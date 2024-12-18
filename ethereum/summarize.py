import os
import re
import yaml
import argparse
from pathlib import Path
from typing import Dict, List, Optional

class ProposalSummarizer:
    def __init__(self, base_path: str, output_path: str, proposal_type: str):
        self.base_path = Path(base_path)
        self.summaries_dir = Path(output_path)
        self.proposal_type = proposal_type.lower()  # 'eip' or 'erc'
        # Create summaries directory if it doesn't exist
        self.summaries_dir.mkdir(exist_ok=True)
        self.token_limits = {
            'short': 128,
            'medium': 256,
            'long': 512
        }

    def extract_frontmatter(self, content: str) -> Dict:
        """Extract YAML frontmatter from proposal content."""
        pattern = r"^---\n(.*?)\n---"
        match = re.search(pattern, content, re.DOTALL)
        if match:
            try:
                metadata = yaml.safe_load(match.group(1))
                # If this is an ERC (based on the proposal_type) but the number is in 'eip' field
                if self.proposal_type == 'erc' and 'erc' not in metadata and 'eip' in metadata:
                    metadata['erc'] = metadata['eip']
                return metadata
            except yaml.YAMLError:
                return {}
        return {}

    def extract_section(self, content: str, section: str) -> Optional[str]:
        """Extract content of a specific section from proposal."""
        pattern = f"## {section}\n(.*?)(?=\n## |$)"
        match = re.search(pattern, content, re.DOTALL)
        return match.group(1).strip() if match else None

    def truncate_to_tokens(self, text: str, max_tokens: int) -> str:
        """Naive token counting - can be replaced with proper tokenizer."""
        words = text.split()
        # Assuming average of 1.3 tokens per word
        word_limit = int(max_tokens / 1.3)
        return ' '.join(words[:word_limit])

    def generate_summary(self, file_path: str, max_tokens: int) -> str:
        """Generate summary for single proposal."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            metadata = self.extract_frontmatter(content)

            # Handle proposal number - try both fields
            proposal_num = 'Unknown'
            if self.proposal_type == 'eip':
                proposal_num = metadata.get('eip', 'Unknown')
            else:  # erc
                proposal_num = metadata.get('erc', metadata.get('eip', 'Unknown'))

            # Handle 'requires' field - convert single int to list
            requires = metadata.get('requires', [])
            if isinstance(requires, int):
                requires = [requires]
            elif requires is None:
                requires = []

            # Calculate token budget for each section
            section_budget = max_tokens // 4

            summary_parts = [
                f"=== {self.proposal_type.upper()}-{proposal_num} ===",
                f"TITLE: {metadata.get('title', 'Unknown')}",
                f"TYPE: {metadata.get('type', 'Unknown')} {metadata.get('category', '')}",
                f"STATUS: {metadata.get('status', 'Unknown')}",
                f"CREATED: {metadata.get('created', 'Unknown')}",
                f"REQUIRES: {', '.join(str(r) for r in requires)}\n"
            ]

            sections = {
                'SUMMARY': self.extract_section(content, 'Abstract'),
                'SPECIFICATION': self.extract_section(content, 'Specification'),
                'MOTIVATION': self.extract_section(content, 'Motivation'),
                'RATIONALE': self.extract_section(content, 'Rationale')
            }

            for section_name, section_content in sections.items():
                if section_content:
                    truncated = self.truncate_to_tokens(section_content, section_budget)
                    summary_parts.append(f"{section_name}:\n{truncated}\n")

            return '\n'.join(summary_parts)
        except Exception as e:
            print(f"Error processing {file_path}: {e}")
            return f"ERROR processing {proposal_num}: {str(e)}\n"

    def process_all_proposals(self):
        """Process all proposals and generate summaries at different token limits."""
        for token_name, token_limit in self.token_limits.items():
            summaries = []

            # Process all .md files in the directory
            for file_path in self.base_path.rglob('*.md'):
                file_lower = file_path.name.lower()
                if f'{self.proposal_type}-' in file_lower:
                    try:
                        # First check if the proposal is moved
                        with open(file_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                        metadata = self.extract_frontmatter(content)

                        # Skip if the proposal is moved
                        if metadata.get('status', '').lower() == 'moved':
                            print(f"Skipping moved {self.proposal_type.upper()}: {file_path}")
                            continue

                        summary = self.generate_summary(str(file_path), token_limit)
                        summaries.append(summary)
                    except Exception as e:
                        print(f"Error processing {file_path}: {e}")

            # Write concatenated summaries to the summaries directory
            output_path = self.summaries_dir / f'{self.proposal_type}_summaries_{token_name}.txt'
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write('\n\n'.join(summaries))

def main():
    parser = argparse.ArgumentParser(description='Generate summaries for Ethereum proposals.')
    parser.add_argument('--type', choices=['eip', 'erc'], required=True,
                      help='Type of proposals to process (eip or erc)')
    parser.add_argument('--input-dir', default='./EIPS',
                      help='Directory containing the proposals')
    parser.add_argument('--output-dir', default='./summaries',
                      help='Directory to store the summaries')

    args = parser.parse_args()

    summarizer = ProposalSummarizer(args.input_dir, args.output_dir, args.type)
    summarizer.process_all_proposals()

if __name__ == "__main__":
    main()
