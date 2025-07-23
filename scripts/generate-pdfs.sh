#!/bin/bash
# generate-pdfs.sh - Generate PDF documentation from markdown files

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if pandoc is installed
if ! command -v pandoc &> /dev/null; then
    echo -e "${RED}Error: pandoc is not installed${NC}"
    echo -e "${YELLOW}Install with:${NC}"
    echo "  macOS: brew install pandoc"
    echo "  Ubuntu: sudo apt install pandoc texlive-latex-base"
    exit 1
fi

# Add TeX to PATH if it exists (for BasicTeX/MacTeX)
if [ -d "/Library/TeX/texbin" ]; then
    export PATH="/Library/TeX/texbin:$PATH"
fi

# Create docs directories
mkdir -p docs/pdf docs/html

echo -e "${BLUE}🔄 Generating documentation files...${NC}"

# First generate HTML files (always works)
echo -e "${BLUE}📄 Generating HTML documentation...${NC}"
pandoc README.md -o docs/html/README.html --toc --toc-depth=3 --number-sections --standalone --css https://cdnjs.cloudflare.com/ajax/libs/github-markdown-css/4.0.0/github-markdown-min.css --metadata title="MCP Manager - README"

pandoc ARCHITECTURE.md -o docs/html/ARCHITECTURE.html --toc --toc-depth=3 --number-sections --standalone --css https://cdnjs.cloudflare.com/ajax/libs/github-markdown-css/4.0.0/github-markdown-min.css --metadata title="MCP Manager - Enterprise Architecture"

pandoc USER_GUIDE.md -o docs/html/USER_GUIDE.html --toc --toc-depth=3 --number-sections --standalone --css https://cdnjs.cloudflare.com/ajax/libs/github-markdown-css/4.0.0/github-markdown-min.css --metadata title="MCP Manager - User Guide"

# Combined HTML
pandoc README.md ARCHITECTURE.md USER_GUIDE.md -o docs/html/MCP-Manager-Complete-Documentation.html \
  --toc --toc-depth=3 --number-sections --standalone \
  --css https://cdnjs.cloudflare.com/ajax/libs/github-markdown-css/4.0.0/github-markdown-min.css \
  --metadata title="MCP Manager - Complete Documentation" \
  --metadata author="MCP Manager Team" \
  --metadata date="$(date +'%B %Y')"

echo -e "${GREEN}✅ HTML generation complete!${NC}"

# Try PDF generation with different engines
echo -e "${BLUE}🔄 Attempting PDF generation...${NC}"

# Try wkhtmltopdf first
if command -v wkhtmltopdf &> /dev/null; then
    echo -e "${BLUE}📄 Using wkhtmltopdf engine...${NC}"
    
    wkhtmltopdf --page-size A4 --margin-top 0.75in --margin-right 0.75in --margin-bottom 0.75in --margin-left 0.75in \
        --enable-toc-back-links --toc --header-right "MCP Manager Documentation" \
        docs/html/README.html docs/pdf/README.pdf
    
    wkhtmltopdf --page-size A4 --margin-top 0.75in --margin-right 0.75in --margin-bottom 0.75in --margin-left 0.75in \
        --enable-toc-back-links --toc --header-right "MCP Manager Architecture" \
        docs/html/ARCHITECTURE.html docs/pdf/ARCHITECTURE.pdf
    
    wkhtmltopdf --page-size A4 --margin-top 0.75in --margin-right 0.75in --margin-bottom 0.75in --margin-left 0.75in \
        --enable-toc-back-links --toc --header-right "MCP Manager User Guide" \
        docs/html/USER_GUIDE.html docs/pdf/USER_GUIDE.pdf
        
    wkhtmltopdf --page-size A4 --margin-top 0.75in --margin-right 0.75in --margin-bottom 0.75in --margin-left 0.75in \
        --enable-toc-back-links --toc --header-right "MCP Manager Complete Documentation" \
        docs/html/MCP-Manager-Complete-Documentation.html docs/pdf/MCP-Manager-Complete-Documentation.pdf
    
    PDF_SUCCESS=true
elif command -v pdflatex &> /dev/null || command -v xelatex &> /dev/null; then
    echo -e "${BLUE}📄 Using LaTeX engine...${NC}"
    
    # Use XeLaTeX for Unicode/emoji support
    if command -v xelatex &> /dev/null; then
        PDF_ENGINE="--pdf-engine=xelatex"
        echo -e "${BLUE}Using XeLaTeX for emoji support...${NC}"
    else
        PDF_ENGINE="--pdf-engine=pdflatex"
        echo -e "${YELLOW}Using pdflatex (emojis may not render)...${NC}"
    fi
    
    # Common pandoc options for professional formatting with Unicode support
    # Don't specify fonts - let XeLaTeX use defaults which should handle emojis better
    PANDOC_OPTS="$PDF_ENGINE --toc --toc-depth=3 --number-sections -V geometry:margin=1in -V colorlinks=true"

    # First, render Mermaid diagrams
    echo -e "${BLUE}🎨 Rendering diagrams...${NC}"
    python3 scripts/render-diagrams.py || echo -e "${YELLOW}Diagram rendering failed, using original files${NC}"
    
    # Check if PDF-ready versions exist, otherwise use originals
    if [ -d "docs/pdf-src" ] && [ -f "docs/pdf-src/README.md" ]; then
        SRC_DIR="docs/pdf-src"
        echo -e "${GREEN}Using PDF-ready versions with rendered diagrams${NC}"
    else
        SRC_DIR="."
        echo -e "${YELLOW}Using original markdown files (diagrams may not render)${NC}"
    fi

    # Individual PDFs
    echo -e "${BLUE}📄 Generating README.pdf...${NC}"
    pandoc "$SRC_DIR/README.md" -o docs/pdf/README.pdf $PANDOC_OPTS --metadata title="MCP Manager - README" || echo -e "${YELLOW}README.pdf generation failed${NC}"
    
    echo -e "${BLUE}🏗️ Generating ARCHITECTURE.pdf...${NC}"
    pandoc "$SRC_DIR/ARCHITECTURE.md" -o docs/pdf/ARCHITECTURE.pdf $PANDOC_OPTS --metadata title="MCP Manager - Enterprise Architecture" || echo -e "${YELLOW}ARCHITECTURE.pdf generation failed${NC}"
    
    echo -e "${BLUE}📖 Generating USER_GUIDE.pdf...${NC}"
    pandoc "$SRC_DIR/USER_GUIDE.md" -o docs/pdf/USER_GUIDE.pdf $PANDOC_OPTS --metadata title="MCP Manager - User Guide" || echo -e "${YELLOW}USER_GUIDE.pdf generation failed${NC}"

    # Combined PDF
    echo -e "${BLUE}📚 Generating complete documentation PDF...${NC}"
    pandoc "$SRC_DIR/README.md" "$SRC_DIR/ARCHITECTURE.md" "$SRC_DIR/USER_GUIDE.md" -o docs/pdf/MCP-Manager-Complete-Documentation.pdf \
      $PANDOC_OPTS \
      --metadata title="MCP Manager - Complete Documentation" \
      --metadata author="MCP Manager Team" \
      --metadata date="$(date +'%B %Y')" || echo -e "${YELLOW}Complete documentation PDF generation failed${NC}"
    
    PDF_SUCCESS=true
else
    echo -e "${YELLOW}⚠️  No PDF engine found (LaTeX or wkhtmltopdf)${NC}"
    echo -e "${BLUE}💡 Alternative PDF generation methods:${NC}"
    echo ""
    echo -e "${YELLOW}Method 1 - Install wkhtmltopdf:${NC}"
    echo "  macOS: brew install wkhtmltopdf"
    echo "  Ubuntu: sudo apt install wkhtmltopdf"
    echo ""
    echo -e "${YELLOW}Method 2 - Install LaTeX:${NC}"
    echo "  macOS: brew install --cask mactex-no-gui"
    echo "  Ubuntu: sudo apt install texlive-latex-base texlive-fonts-recommended"
    echo ""
    echo -e "${YELLOW}Method 3 - Browser PDF printing:${NC}"
    echo "  1. Open the HTML files in docs/html/ with your browser"
    echo "  2. Use browser Print → Save as PDF"
    echo "  3. Recommended settings: A4, margins 0.75in, include headers/footers"
    echo ""
    PDF_SUCCESS=false
fi

echo -e "${GREEN}✅ Documentation generation complete!${NC}"

if [ "$PDF_SUCCESS" = true ]; then
    # Create a professional cover page for PDF
    cat > docs/pdf/cover.md << 'EOF'
---
title: "MCP Manager"
subtitle: "Enterprise-Grade Model Context Protocol Server Management"
author: "Development Team"
date: "July 2025"
geometry: "margin=1in"
---

\newpage

# Documentation Suite

This documentation package contains:

1. **README** - Project overview and quick start guide
2. **ARCHITECTURE** - Enterprise technical architecture and developer documentation  
3. **USER GUIDE** - Comprehensive user documentation with examples and workflows

For the latest updates, visit: https://github.com/blemis/mcp-manager-python

---

*Version 1.0 - Professional Documentation Suite*
EOF

    # Generate PDF with cover page if LaTeX is available
    if command -v pdflatex &> /dev/null || command -v xelatex &> /dev/null; then
        echo -e "${BLUE}📋 Generating complete documentation with cover page...${NC}"
        pandoc docs/pdf/cover.md "$SRC_DIR/README.md" "$SRC_DIR/ARCHITECTURE.md" "$SRC_DIR/USER_GUIDE.md" -o docs/pdf/MCP-Manager-Professional-Documentation.pdf \
          $PANDOC_OPTS \
          --metadata title="MCP Manager Professional Documentation" \
          --metadata author="MCP Manager Development Team" \
          --metadata date="$(date +'%B %Y')"
    fi

    # Clean up temporary files
    rm -f docs/pdf/cover.md

    echo -e "${GREEN}✅ PDF generation complete!${NC}"
    echo -e "${BLUE}Generated PDF files:${NC}"
    ls -la docs/pdf/*.pdf 2>/dev/null && ls -lh docs/pdf/*.pdf | awk '{print "  📄 " $9 ": " $5}' || echo "  No PDF files generated"
fi

echo -e "${BLUE}Generated HTML files:${NC}"
ls -lh docs/html/*.html | awk '{print "  🌐 " $9 ": " $5}'

echo ""
echo -e "${YELLOW}💡 Usage Tips:${NC}"
echo "  • HTML files can be opened directly in your browser"
echo "  • For PDF from HTML: Open HTML file → Print → Save as PDF"
echo "  • Professional formatting with tables of contents included"
echo "  • All files are self-contained and portable"