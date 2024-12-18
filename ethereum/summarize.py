import os
import re
import yaml
from pathlib import Path
from typing import Dict, List, Optional

class EIPSummarizer:
    def __init__(self, base_path: str, output_path: str):
        self.base_path = Path(base_path)
        self.summaries_dir = Path(output_path)
        # Create summaries directory if it doesn't exist
        self.summaries_dir.mkdir(exist_ok=True)
        self.token_limits = {
            'short': 128,
            'medium': 256,
            'long': 512
        }

    def extract_frontmatter(self, content: str) -> Dict:
        """Extract YAML frontmatter from EIP content."""
        pattern = r"^---\n(.*?)\n---"
        match = re.search(pattern, content, re.DOTALL)
        if match:
            try:
                return yaml.safe_load(match.group(1))
            except yaml.YAMLError:
                return {}
        return {}

    def extract_section(self, content: str, section: str) -> Optional[str]:
        """Extract content of a specific section from EIP."""
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
        """Generate summary for single EIP."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            metadata = self.extract_frontmatter(content)

            # Handle 'requires' field - convert single int to list
            requires = metadata.get('requires', [])
            if isinstance(requires, int):
                requires = [requires]
            elif requires is None:
                requires = []

            # Calculate token budget for each section
            section_budget = max_tokens // 4  # Divide tokens between sections

            summary_parts = [
                f"=== EIP-{metadata.get('eip', 'Unknown')} ===",
                f"TITLE: {metadata.get('title', 'Unknown')}",
                f"TYPE: {metadata.get('type', 'Unknown')} {metadata.get('category', '')}",
                f"STATUS: {metadata.get('status', 'Unknown')}",
                f"CREATED: {metadata.get('created', 'Unknown')}",
                f"REQUIRES: {', '.join(str(r) for r in requires)}\n"
            ]

            # Extract and truncate main sections
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
            return f"ERROR processing {metadata.get('eip', 'Unknown')}: {str(e)}\n"


    def process_all_eips(self):
        """Process all EIPs and generate summaries at different token limits."""
        for token_name, token_limit in self.token_limits.items():
            summaries = []

            # Process all .md files in the directory
            for file_path in self.base_path.rglob('*.md'):
                if 'eip-' in file_path.name.lower():
                    try:
                        # First check if the EIP is moved
                        with open(file_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                        metadata = self.extract_frontmatter(content)

                        # Skip if the EIP is moved
                        if metadata.get('status', '').lower() == 'moved':
                            print(f"Skipping moved EIP: {file_path}")
                            continue

                        summary = self.generate_summary(str(file_path), token_limit)
                        summaries.append(summary)
                    except Exception as e:
                        print(f"Error processing {file_path}: {e}")

            # Write concatenated summaries to the summaries directory
            output_path = self.summaries_dir / f'eip_summaries_{token_name}.txt'
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write('\n\n'.join(summaries))

def main():
    # Adjust path to your EIPs directory
    summarizer = EIPSummarizer('./EIPS', './ethereum')
    summarizer.process_all_eips()

if __name__ == "__main__":
    main()
