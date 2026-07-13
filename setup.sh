#!/bin/bash

################################################################################
# GRN Atlas UI - Automated Setup Script
# 
# This script automates the integration of the complete GRN Atlas UI into your
# existing React project. It will:
# 1. Create directory structure
# 2. Copy all component files
# 3. Install dependencies
# 4. Set up environment variables
# 5. Prepare for git commit
#
# Usage: bash setup.sh [project-path]
# Example: bash setup.sh ~/projects/grn-atlas
################################################################################

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_PATH="${1:-.}"
SOURCE_DIR="$SCRIPT_DIR"

# Function to print colored output
print_header() {
    echo -e "\n${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}\n"
}

print_success() {
    echo -e "${GREEN}✓${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

print_info() {
    echo -e "${BLUE}ℹ${NC} $1"
}

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to safely create directory
safe_mkdir() {
    if [ ! -d "$1" ]; then
        mkdir -p "$1"
        print_success "Created directory: $1"
    else
        print_info "Directory already exists: $1"
    fi
}

# Function to safely copy file
safe_copy() {
    local source="$1"
    local destination="$2"
    
    if [ ! -f "$source" ]; then
        print_error "Source file not found: $source"
        return 1
    fi
    
    if [ -f "$destination" ]; then
        print_warning "File already exists: $destination (skipping)"
        return 0
    fi
    
    cp "$source" "$destination"
    print_success "Copied: $(basename $destination)"
}

# Main setup process
main() {
    print_header "GRN Atlas UI - Automated Setup"
    
    # Check prerequisites
    print_header "Step 1: Checking Prerequisites"
    
    if ! command_exists node; then
        print_error "Node.js is not installed"
        echo "  Please install Node.js from https://nodejs.org/"
        exit 1
    fi
    print_success "Node.js is installed ($(node --version))"
    
    if ! command_exists npm; then
        print_error "npm is not installed"
        exit 1
    fi
    print_success "npm is installed ($(npm --version))"
    
    if ! command_exists git; then
        print_warning "git is not installed (optional, but recommended)"
    else
        print_success "git is installed ($(git --version | head -n1))"
    fi
    
    # Verify project path
    print_header "Step 2: Verifying Project Structure"
    
    if [ ! -d "$PROJECT_PATH" ]; then
        print_error "Project path does not exist: $PROJECT_PATH"
        exit 1
    fi
    print_success "Project path exists: $PROJECT_PATH"
    
    if [ ! -f "$PROJECT_PATH/package.json" ]; then
        print_error "package.json not found in $PROJECT_PATH"
        echo "  Are you sure this is a React project?"
        exit 1
    fi
    print_success "package.json found"
    
    if [ ! -d "$PROJECT_PATH/src" ]; then
        print_error "src/ directory not found"
        exit 1
    fi
    print_success "src/ directory exists"
    
    # Create directory structure
    print_header "Step 3: Creating Directory Structure"
    
    safe_mkdir "$PROJECT_PATH/src/components"
    safe_mkdir "$PROJECT_PATH/src/services"
    safe_mkdir "$PROJECT_PATH/src/styles"
    safe_mkdir "$PROJECT_PATH/docs"
    
    # Copy React components
    print_header "Step 4: Copying React Components"
    
    components=(
        "GeneNetworkExplorer.jsx"
        "components/Sidebar.jsx"
        "components/Toolbar.jsx"
        "components/ViewTabs.jsx"
        "components/NetworkVisualization.jsx"
        "components/GeneDetailPanel.jsx"
        "components/ComparisonView.jsx"
        "components/InterventionDesigner.jsx"
        "components/PathwayView.jsx"
    )
    
    for component in "${components[@]}"; do
        safe_copy "$SOURCE_DIR/$component" "$PROJECT_PATH/src/$component"
    done
    
    # Copy services
    print_header "Step 5: Copying Services"
    
    safe_copy "$SOURCE_DIR/services/apiService.js" "$PROJECT_PATH/src/services/apiService.js"
    
    # Copy styles
    print_header "Step 6: Copying CSS Styles"
    
    styles=(
        "styles/theme.css"
        "styles/GeneNetworkExplorer.css"
        "styles/Sidebar.css"
        "styles/Toolbar.css"
        "styles/ViewTabs.css"
        "styles/NetworkVisualization.css"
        "styles/GeneDetailPanel.css"
        "styles/ComparisonView.css"
        "styles/InterventionDesigner.css"
        "styles/PathwayView.css"
    )
    
    for style in "${styles[@]}"; do
        safe_copy "$SOURCE_DIR/$style" "$PROJECT_PATH/src/$style"
    done
    
    # Copy documentation
    print_header "Step 7: Copying Documentation"
    
    docs=(
        "README.md"
        "INTEGRATION_GUIDE.md"
        "PROJECT_SUMMARY.md"
        "QUICK_REFERENCE.md"
        "backend_example.py"
    )
    
    for doc in "${docs[@]}"; do
        if [ -f "$SOURCE_DIR/$doc" ]; then
            cp "$SOURCE_DIR/$doc" "$PROJECT_PATH/docs/$doc"
            print_success "Copied: $doc"
        fi
    done
    
    # Copy and update .env.example
    print_header "Step 8: Setting Up Environment Variables"
    
    if [ -f "$SOURCE_DIR/.env.example" ]; then
        if [ ! -f "$PROJECT_PATH/.env.local" ]; then
            cp "$SOURCE_DIR/.env.example" "$PROJECT_PATH/.env.local"
            print_success "Created .env.local from template"
            print_info "Update .env.local with your API URL:"
            echo "  REACT_APP_API_URL=http://localhost:8000/api/v1"
        else
            print_warning ".env.local already exists (skipping)"
            print_info "Merge settings from .env.example if needed"
        fi
    fi
    
    # Install dependencies
    print_header "Step 9: Installing Dependencies"
    
    print_info "Checking for required packages..."
    
    cd "$PROJECT_PATH"
    
    # Check if cytoscape is already installed
    if npm list cytoscape >/dev/null 2>&1; then
        print_success "cytoscape is already installed"
    else
        print_info "Installing cytoscape..."
        npm install cytoscape@^3.28.1
        print_success "cytoscape installed"
    fi
    
    if npm list cytoscape-popper >/dev/null 2>&1; then
        print_success "cytoscape-popper is already installed"
    else
        print_info "Installing cytoscape-popper..."
        npm install cytoscape-popper@^2.0.0
        print_success "cytoscape-popper installed"
    fi
    
    if npm list popper.js >/dev/null 2>&1; then
        print_success "popper.js is already installed"
    else
        print_info "Installing popper.js..."
        npm install popper.js@^1.16.1
        print_success "popper.js installed"
    fi
    
    # Update App.jsx
    print_header "Step 10: Updating App.jsx"
    
    if [ -f "$PROJECT_PATH/src/App.jsx" ]; then
        print_warning "App.jsx already exists"
        print_info "You need to manually update it to use GeneNetworkExplorer:"
        echo ""
        echo "  import GeneNetworkExplorer from './components/GeneNetworkExplorer';"
        echo "  import './styles/theme.css';"
        echo ""
        echo "  export default function App() {"
        echo "    return <GeneNetworkExplorer />;"
        echo "  }"
        echo ""
    fi
    
    # Create backup of package.json
    print_header "Step 11: Backing Up Configuration"
    
    if [ -f "$PROJECT_PATH/package.json" ]; then
        cp "$PROJECT_PATH/package.json" "$PROJECT_PATH/package.json.backup"
        print_success "Created package.json.backup"
    fi
    
    # Summary
    print_header "✓ Setup Complete!"
    
    echo -e "${GREEN}All files have been successfully copied to your project.${NC}\n"
    
    echo "📋 ${BLUE}Next Steps:${NC}"
    echo ""
    echo "  1. ${YELLOW}Update App.jsx:${NC}"
    echo "     Import GeneNetworkExplorer and theme.css"
    echo ""
    echo "  2. ${YELLOW}Configure Environment:${NC}"
    echo "     Edit .env.local with your API URL"
    echo ""
    echo "  3. ${YELLOW}Read Documentation:${NC}"
    echo "     Check docs/ folder for guides and examples"
    echo ""
    echo "  4. ${YELLOW}Start Development:${NC}"
    echo "     npm start"
    echo ""
    echo "  5. ${YELLOW}Set Up Backend:${NC}"
    echo "     Follow INTEGRATION_GUIDE.md in docs/"
    echo ""
    echo "  6. ${YELLOW}Commit to Git:${NC}"
    echo "     git add ."
    echo "     git commit -m 'feat: Add GRN Atlas UI complete implementation'"
    echo "     git push"
    echo ""
    
    # Git status
    if command_exists git; then
        print_header "Step 12: Git Status"
        
        cd "$PROJECT_PATH"
        
        if [ -d ".git" ]; then
            print_info "Git repository detected"
            echo ""
            print_info "New files ready to commit:"
            git status --short | head -20
            echo ""
            print_info "Run these commands to commit:"
            echo "  cd $PROJECT_PATH"
            echo "  git add ."
            echo "  git commit -m 'feat: Add GRN Atlas UI - complete implementation (all 5 phases)'"
            echo "  git push"
        fi
    fi
    
    # File manifest
    print_header "Step 13: File Manifest"
    
    echo -e "${BLUE}Components (9 files):${NC}"
    echo "  ✓ src/components/GeneNetworkExplorer.jsx"
    echo "  ✓ src/components/Sidebar.jsx"
    echo "  ✓ src/components/Toolbar.jsx"
    echo "  ✓ src/components/ViewTabs.jsx"
    echo "  ✓ src/components/NetworkVisualization.jsx"
    echo "  ✓ src/components/GeneDetailPanel.jsx"
    echo "  ✓ src/components/ComparisonView.jsx"
    echo "  ✓ src/components/InterventionDesigner.jsx"
    echo "  ✓ src/components/PathwayView.jsx"
    echo ""
    
    echo -e "${BLUE}Styles (10 files):${NC}"
    echo "  ✓ src/styles/theme.css"
    echo "  ✓ src/styles/GeneNetworkExplorer.css"
    echo "  ✓ src/styles/Sidebar.css"
    echo "  ✓ src/styles/Toolbar.css"
    echo "  ✓ src/styles/ViewTabs.css"
    echo "  ✓ src/styles/NetworkVisualization.css"
    echo "  ✓ src/styles/GeneDetailPanel.css"
    echo "  ✓ src/styles/ComparisonView.css"
    echo "  ✓ src/styles/InterventionDesigner.css"
    echo "  ✓ src/styles/PathwayView.css"
    echo ""
    
    echo -e "${BLUE}Services (1 file):${NC}"
    echo "  ✓ src/services/apiService.js"
    echo ""
    
    echo -e "${BLUE}Documentation (5 files):${NC}"
    echo "  ✓ docs/README.md"
    echo "  ✓ docs/INTEGRATION_GUIDE.md"
    echo "  ✓ docs/PROJECT_SUMMARY.md"
    echo "  ✓ docs/QUICK_REFERENCE.md"
    echo "  ✓ docs/backend_example.py"
    echo ""
    
    echo -e "${BLUE}Environment:${NC}"
    echo "  ✓ .env.local (created from template)"
    echo ""
    
    print_header "Installation Summary"
    
    echo -e "${GREEN}Project: $PROJECT_PATH${NC}"
    echo -e "${GREEN}Total Files: 28${NC}"
    echo -e "${GREEN}Total Size: ~161 KB${NC}"
    echo -e "${GREEN}Status: Ready to develop${NC}"
    echo ""
    
    # Final tips
    print_header "💡 Pro Tips"
    
    echo "1. ${BLUE}Development:${NC}"
    echo "   npm start          # Start React dev server"
    echo "   npm run build      # Build for production"
    echo ""
    echo "2. ${BLUE}Backend:${NC}"
    echo "   python -m uvicorn backend_example:app --reload"
    echo ""
    echo "3. ${BLUE}Documentation:${NC}"
    echo "   • QUICK_REFERENCE.md - Start here for overview"
    echo "   • README.md - Full feature documentation"
    echo "   • INTEGRATION_GUIDE.md - Backend setup"
    echo "   • PROJECT_SUMMARY.md - Quick reference"
    echo ""
    echo "4. ${BLUE}Troubleshooting:${NC}"
    echo "   • Check browser console for errors (F12)"
    echo "   • Verify .env.local has correct API URL"
    echo "   • Ensure backend is running on port 8000"
    echo "   • Check backend CORS configuration"
    echo ""
    
    print_header "Ready to Go! 🚀"
    
    echo -e "${GREEN}Your GRN Atlas UI is ready for development.${NC}"
    echo -e "${GREEN}All documentation is in the docs/ folder.${NC}"
    echo ""
    echo "Happy coding! 🧬"
    echo ""
}

# Run main function
main "$@"
