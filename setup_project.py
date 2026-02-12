# setup_project.py
import os

def create_project_structure():
    """Create the complete project directory structure"""
    
    directories = [
        'data/raw/earthquakes',
        'data/raw/floods',
        'data/processed',
        'data/alerts',
        'models',
        'src/collectors',
        'src/predictors',
        'src/alert_system',
        'src/utils',
        'dashboard',
        'notebooks',
        'config',
        'logs'
    ]
    
    for directory in directories:
        os.makedirs(directory, exist_ok=True)
        # Create __init__.py for Python packages
        if directory.startswith('src/'):
            init_file = os.path.join(directory, '__init__.py')
            open(init_file, 'a').close()
    
    print("✓ Project structure created successfully!")
    
    # Create .gitignore
    gitignore_content = """
# Data files
data/raw/
*.csv
*.pkl

# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
env/
venv/

# Logs
logs/
*.log

# IDE
.vscode/
.idea/
*.Rproj

# Config with sensitive info
config/secrets.yaml
"""
    
    with open('.gitignore', 'w') as f:
        f.write(gitignore_content)
    
    print("✓ .gitignore created!")

if __name__ == "__main__":
    create_project_structure()