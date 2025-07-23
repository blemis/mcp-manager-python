#!/usr/bin/env python3
"""
Extract and render Mermaid diagrams from markdown files
"""
import re
import os
import subprocess
import sys
from pathlib import Path

def extract_mermaid_blocks(content, filename):
    """Extract Mermaid code blocks and return content with image references"""
    diagrams = []
    counter = 1
    
    # Pattern to match mermaid code blocks
    pattern = r'```mermaid\n(.*?)\n```'
    
    def replace_mermaid(match):
        nonlocal counter
        mermaid_code = match.group(1)
        diagram_name = f"{filename}-diagram-{counter}"
        diagrams.append((diagram_name, mermaid_code))
        
        # Replace with image reference for PDF
        image_ref = f"![Diagram {counter}](docs/diagrams/{diagram_name}.png)"
        counter += 1
        return image_ref
    
    # Replace all mermaid blocks with image references
    updated_content = re.sub(pattern, replace_mermaid, content, flags=re.DOTALL)
    
    return updated_content, diagrams

def render_diagram(name, code, output_dir):
    """Render a single Mermaid diagram to PNG"""
    mermaid_file = output_dir / f"{name}.mmd"
    png_file = output_dir / f"{name}.png"
    
    # Write mermaid code to file
    with open(mermaid_file, 'w') as f:
        f.write(code)
    
    # Render with mermaid-cli
    try:
        subprocess.run([
            'mmdc', '-i', str(mermaid_file), '-o', str(png_file),
            '-t', 'neutral', '-b', 'white', '-w', '1200', '-H', '800'
        ], check=True)
        print(f"✅ Rendered {name}.png")
        
        # Clean up temporary mermaid file
        mermaid_file.unlink()
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to render {name}: {e}")
        return False
    except FileNotFoundError:
        print("❌ mermaid-cli (mmdc) not found. Install with: npm install -g @mermaid-js/mermaid-cli")
        return False

def main():
    # Create output directories
    diagrams_dir = Path("docs/diagrams")
    pdf_docs_dir = Path("docs/pdf-src")
    
    diagrams_dir.mkdir(parents=True, exist_ok=True)
    pdf_docs_dir.mkdir(parents=True, exist_ok=True)
    
    markdown_files = ['README.md', 'ARCHITECTURE.md', 'USER_GUIDE.md']
    
    print("🔄 Extracting and rendering Mermaid diagrams...")
    
    all_diagrams_rendered = True
    
    for md_file in markdown_files:
        if not Path(md_file).exists():
            print(f"⚠️  {md_file} not found, skipping...")
            continue
            
        print(f"\n📄 Processing {md_file}...")
        
        # Read the original file
        with open(md_file, 'r') as f:
            content = f.read()
        
        # Extract diagrams and get updated content
        filename_base = md_file.replace('.md', '')
        updated_content, diagrams = extract_mermaid_blocks(content, filename_base)
        
        # Render each diagram
        for diagram_name, diagram_code in diagrams:
            success = render_diagram(diagram_name, diagram_code, diagrams_dir)
            if not success:
                all_diagrams_rendered = False
        
        # Write PDF-ready version
        pdf_file = pdf_docs_dir / md_file
        with open(pdf_file, 'w') as f:
            f.write(updated_content)
        
        print(f"📝 Created PDF-ready version: {pdf_file}")
    
    if all_diagrams_rendered:
        print("\n✅ All diagrams rendered successfully!")
        print(f"📁 Diagrams saved to: {diagrams_dir}")
        print(f"📁 PDF-ready markdown saved to: {pdf_docs_dir}")
    else:
        print("\n⚠️  Some diagrams failed to render")
        sys.exit(1)

if __name__ == "__main__":
    main()