#!/usr/bin/env python3
"""
GitHub-style PDF generator using Playwright MCP
Creates PDFs that look exactly like GitHub's markdown rendering
"""
import asyncio
import json
import subprocess
import sys
from pathlib import Path

def create_github_style_html(markdown_file, output_html):
    """Create GitHub-style HTML from markdown using GitHub's CSS"""
    
    markdown_path = Path(markdown_file)
    if not markdown_path.exists():
        print(f"❌ Markdown file not found: {markdown_file}")
        return False
        
    # Read the markdown content
    with open(markdown_path, 'r') as f:
        markdown_content = f.read()
    
    # Create GitHub-style HTML template
    html_template = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{markdown_path.stem}</title>
    
    <!-- GitHub Primer CSS -->
    <link rel="stylesheet" href="https://unpkg.com/@primer/css@21/dist/primer.css">
    
    <!-- GitHub Markdown CSS -->
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/github-markdown-css/5.2.0/github-markdown.min.css">
    
    <!-- Mermaid for diagrams -->
    <script src="https://unpkg.com/mermaid@10/dist/mermaid.min.js"></script>
    
    <!-- Highlight.js for code highlighting -->
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.8.0/styles/github.min.css">
    <script src="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.8.0/highlight.min.js"></script>
    
    <!-- Markdown-it for parsing -->
    <script src="https://cdn.jsdelivr.net/npm/markdown-it@13/dist/markdown-it.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/markdown-it-emoji@2/dist/markdown-it-emoji.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/markdown-it-anchor@8/dist/markdownItAnchor.umd.js"></script>
    
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Noto Sans', Helvetica, Arial, sans-serif;
            background-color: #ffffff;
            margin: 0;
            padding: 20px;
            line-height: 1.6;
        }}
        .container {{
            max-width: 1012px;
            margin: 0 auto;
            padding: 20px;
        }}
        .markdown-body {{
            background-color: #ffffff;
            padding: 45px;
            border-radius: 6px;
            box-shadow: 0 0 0 1px rgba(27,31,36,0.15);
        }}
        
        /* Enhanced code blocks like GitHub */
        .markdown-body pre {{
            background-color: #f6f8fa;
            border-radius: 6px;
            font-size: 85%;
            line-height: 1.45;
            overflow: auto;
            padding: 16px;
        }}
        
        /* Table styling like GitHub */
        .markdown-body table {{
            border-spacing: 0;
            border-collapse: collapse;
            display: block;
            width: max-content;
            max-width: 100%;
            overflow: auto;
        }}
        
        .markdown-body table th,
        .markdown-body table td {{
            padding: 6px 13px;
            border: 1px solid #d0d7de;
        }}
        
        .markdown-body table th {{
            background-color: #f6f8fa;
            font-weight: 600;
        }}
        
        /* Mermaid diagram styling */
        .mermaid {{
            text-align: center;
            margin: 1em 0;
        }}
        
        /* Print styles for PDF */
        @media print {{
            body {{
                background: white !important;
                color: black !important;
            }}
            .container {{
                max-width: none;
                margin: 0;
                padding: 0;
            }}
            .markdown-body {{
                box-shadow: none;
                border: none;
                padding: 20px;
            }}
        }}
        
        /* Custom emoji styling */
        .emoji {{
            height: 1em;
            width: 1em;
            margin: 0 0.05em 0 0.1em;
            vertical-align: -0.1em;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="markdown-body" id="markdown-content">
            <!-- Markdown content will be inserted here -->
        </div>
    </div>
    
    <script>
        // Initialize Mermaid
        mermaid.initialize({{
            startOnLoad: true,
            theme: 'default',
            themeVariables: {{
                primaryColor: '#0366d6',
                primaryTextColor: '#24292f',
                primaryBorderColor: '#d0d7de',
                lineColor: '#656d76',
                secondaryColor: '#f6f8fa',
                tertiaryColor: '#ffffff'
            }}
        }});
        
        // Configure markdown-it with GitHub-like settings
        const md = window.markdownit({{
            html: true,
            linkify: true,
            typographer: true,
            highlight: function (str, lang) {{
                if (lang && hljs.getLanguage(lang)) {{
                    try {{
                        return '<pre class="hljs"><code>' +
                               hljs.highlight(str, {{ language: lang, ignoreIllegals: true }}).value +
                               '</code></pre>';
                    }} catch (__) {{}}
                }}
                return '<pre class="hljs"><code>' + md.utils.escapeHtml(str) + '</code></pre>';
            }}
        }})
        .use(window.markdownItEmoji)
        .use(window.markdownItAnchor, {{
            permalink: true,
            permalinkBefore: true,
            permalinkSymbol: '#'
        }});
        
        // Render the markdown
        const markdownSource = `{markdown_content.replace('`', '\\`').replace('$', '\\$')}`;
        const result = md.render(markdownSource);
        document.getElementById('markdown-content').innerHTML = result;
        
        // Initialize highlight.js for any remaining code blocks
        hljs.highlightAll();
        
        // Wait for Mermaid to render, then signal ready for PDF
        setTimeout(() => {{
            document.body.classList.add('ready-for-pdf');
        }}, 2000);
    </script>
</body>
</html>"""
    
    # Write the HTML file
    with open(output_html, 'w') as f:
        f.write(html_template)
    
    print(f"✅ Created GitHub-style HTML: {output_html}")
    return True

async def generate_pdf_with_playwright(html_file, output_pdf):
    """Generate PDF from HTML using Playwright MCP"""
    try:
        # Use Claude's Playwright MCP to generate the PDF
        print(f"🎭 Generating PDF using Playwright MCP...")
        
        # Create a simple script that will be executed by Playwright MCP
        playwright_script = f"""
        const {{ chromium }} = require('playwright');
        
        (async () => {{
            const browser = await chromium.launch();
            const page = await browser.newPage();
            
            // Load the HTML file
            await page.goto('file://{Path(html_file).absolute()}', {{ waitUntil: 'networkidle' }});
            
            // Wait for content to be ready
            await page.waitForSelector('.ready-for-pdf', {{ timeout: 10000 }});
            
            // Generate PDF with high quality settings
            await page.pdf({{
                path: '{output_pdf}',
                format: 'A4',
                margin: {{ top: '1cm', right: '1cm', bottom: '1cm', left: '1cm' }},
                printBackground: true,
                preferCSSPageSize: false
            }});
            
            await browser.close();
            console.log('✅ PDF generated successfully: {output_pdf}');
        }})().catch(console.error);
        """
        
        # Write the script to a temporary file
        script_file = Path(output_pdf).parent / "temp_playwright_script.js"
        with open(script_file, 'w') as f:
            f.write(playwright_script)
        
        # Execute the script using Node.js
        result = subprocess.run([
            'node', str(script_file)
        ], capture_output=True, text=True, timeout=30)
        
        if result.returncode == 0:
            print(f"✅ Successfully generated PDF: {output_pdf}")
            # Clean up temporary script
            script_file.unlink()
            return True
        else:
            print(f"❌ Playwright script failed: {result.stderr}")
            return False
            
    except subprocess.TimeoutExpired:
        print("❌ Playwright PDF generation timed out")
        return False
    except Exception as e:
        print(f"❌ Error generating PDF: {e}")
        return False

def main():
    """Main function to generate GitHub-style PDFs"""
    print("🚀 GitHub-Style PDF Generator")
    print("=" * 50)
    
    # Create output directories
    html_dir = Path("docs/github-html")
    pdf_dir = Path("docs/github-pdf")
    
    html_dir.mkdir(parents=True, exist_ok=True)
    pdf_dir.mkdir(parents=True, exist_ok=True)
    
    # Files to process
    markdown_files = ['README.md', 'ARCHITECTURE.md', 'USER_GUIDE.md']
    
    for md_file in markdown_files:
        print(f"\n📄 Processing {md_file}...")
        
        if not Path(md_file).exists():
            print(f"⚠️  {md_file} not found, skipping...")
            continue
        
        # Create HTML version
        html_file = html_dir / f"{Path(md_file).stem}.html"
        if create_github_style_html(md_file, html_file):
            
            # Generate PDF
            pdf_file = pdf_dir / f"{Path(md_file).stem}.pdf"
            success = asyncio.run(generate_pdf_with_playwright(html_file, pdf_file))
            
            if success:
                print(f"✅ Generated: {pdf_file}")
            else:
                print(f"❌ Failed to generate: {pdf_file}")
    
    # Create combined documentation
    print(f"\n📚 Creating combined documentation...")
    combined_html = html_dir / "Complete-Documentation.html"
    combined_md_content = ""
    
    for md_file in markdown_files:
        if Path(md_file).exists():
            with open(md_file, 'r') as f:
                combined_md_content += f"\\n\\n{f.read()}\\n\\n---\\n\\n"
    
    if create_github_style_html_from_content(combined_md_content, combined_html):
        combined_pdf = pdf_dir / "MCP-Manager-Complete-Documentation.pdf"
        success = asyncio.run(generate_pdf_with_playwright(combined_html, combined_pdf))
        
        if success:
            print(f"✅ Generated combined PDF: {combined_pdf}")
    
    print(f"\n🎉 GitHub-style PDF generation complete!")
    print(f"📁 HTML files: {html_dir}")
    print(f"📁 PDF files: {pdf_dir}")

def create_github_style_html_from_content(content, output_html):
    """Create HTML from markdown content string"""
    # Same as create_github_style_html but takes content directly
    html_template = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>MCP Manager - Complete Documentation</title>
    
    <!-- GitHub Primer CSS -->
    <link rel="stylesheet" href="https://unpkg.com/@primer/css@21/dist/primer.css">
    
    <!-- GitHub Markdown CSS -->
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/github-markdown-css/5.2.0/github-markdown.min.css">
    
    <!-- Mermaid for diagrams -->
    <script src="https://unpkg.com/mermaid@10/dist/mermaid.min.js"></script>
    
    <!-- Highlight.js for code highlighting -->
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.8.0/styles/github.min.css">
    <script src="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.8.0/highlight.min.js"></script>
    
    <!-- Markdown-it for parsing -->
    <script src="https://cdn.jsdelivr.net/npm/markdown-it@13/dist/markdown-it.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/markdown-it-emoji@2/dist/markdown-it-emoji.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/markdown-it-anchor@8/dist/markdownItAnchor.umd.js"></script>
    
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Noto Sans', Helvetica, Arial, sans-serif;
            background-color: #ffffff;
            margin: 0;
            padding: 20px;
            line-height: 1.6;
        }}
        .container {{
            max-width: 1012px;
            margin: 0 auto;
            padding: 20px;
        }}
        .markdown-body {{
            background-color: #ffffff;
            padding: 45px;
            border-radius: 6px;
            box-shadow: 0 0 0 1px rgba(27,31,36,0.15);
        }}
        
        /* Enhanced code blocks like GitHub */
        .markdown-body pre {{
            background-color: #f6f8fa;
            border-radius: 6px;
            font-size: 85%;
            line-height: 1.45;
            overflow: auto;
            padding: 16px;
        }}
        
        /* Table styling like GitHub */
        .markdown-body table {{
            border-spacing: 0;
            border-collapse: collapse;
            display: block;
            width: max-content;
            max-width: 100%;
            overflow: auto;
        }}
        
        .markdown-body table th,
        .markdown-body table td {{
            padding: 6px 13px;
            border: 1px solid #d0d7de;
        }}
        
        .markdown-body table th {{
            background-color: #f6f8fa;
            font-weight: 600;
        }}
        
        /* Mermaid diagram styling */
        .mermaid {{
            text-align: center;
            margin: 1em 0;
        }}
        
        /* Print styles for PDF */
        @media print {{
            body {{
                background: white !important;
                color: black !important;
            }}
            .container {{
                max-width: none;
                margin: 0;
                padding: 0;
            }}
            .markdown-body {{
                box-shadow: none;
                border: none;
                padding: 20px;
            }}
        }}
        
        /* Custom emoji styling */
        .emoji {{
            height: 1em;
            width: 1em;
            margin: 0 0.05em 0 0.1em;
            vertical-align: -0.1em;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="markdown-body" id="markdown-content">
            <!-- Markdown content will be inserted here -->
        </div>
    </div>
    
    <script>
        // Initialize Mermaid
        mermaid.initialize({{
            startOnLoad: true,
            theme: 'default',
            themeVariables: {{
                primaryColor: '#0366d6',
                primaryTextColor: '#24292f',
                primaryBorderColor: '#d0d7de',
                lineColor: '#656d76',
                secondaryColor: '#f6f8fa',
                tertiaryColor: '#ffffff'
            }}
        }});
        
        // Configure markdown-it with GitHub-like settings
        const md = window.markdownit({{
            html: true,
            linkify: true,
            typographer: true,
            highlight: function (str, lang) {{
                if (lang && hljs.getLanguage(lang)) {{
                    try {{
                        return '<pre class="hljs"><code>' +
                               hljs.highlight(str, {{ language: lang, ignoreIllegals: true }}).value +
                               '</code></pre>';
                    }} catch (__) {{}}
                }}
                return '<pre class="hljs"><code>' + md.utils.escapeHtml(str) + '</code></pre>';
            }}
        }})
        .use(window.markdownItEmoji)
        .use(window.markdownItAnchor, {{
            permalink: true,
            permalinkBefore: true,
            permalinkSymbol: '#'
        }});
        
        // Render the markdown
        const markdownSource = `{content.replace('`', '\\`').replace('$', '\\$')}`;
        const result = md.render(markdownSource);
        document.getElementById('markdown-content').innerHTML = result;
        
        // Initialize highlight.js for any remaining code blocks
        hljs.highlightAll();
        
        // Wait for Mermaid to render, then signal ready for PDF
        setTimeout(() => {{
            document.body.classList.add('ready-for-pdf');
        }}, 2000);
    </script>
</body>
</html>"""
    
    # Write the HTML file
    with open(output_html, 'w') as f:
        f.write(html_template)
    
    return True

if __name__ == "__main__":
    main()