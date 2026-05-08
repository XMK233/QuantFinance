---
name: "notebook-cleaner"
description: "Cleans Jupyter Notebook files by removing cell outputs. Invoke when user wants to remove cell outputs from .ipynb files without opening them."
---

# Notebook Cleaner

This skill provides command-line tools to clean Jupyter Notebook (.ipynb) files by removing cell outputs, execution counts, and metadata without needing to open the notebook files.

## Available Methods

### 1. Using nbconvert (Recommended)
```bash
# Clean single notebook file
jupyter nbconvert --ClearOutputPreprocessor.enabled=True --inplace /path/to/notebook.ipynb

# Clean all notebooks in directory
find . -name "*.ipynb" -exec jupyter nbconvert --ClearOutputPreprocessor.enabled=True --inplace {} \;
```

### 2. Using Python script
```python
import json
import sys

def clean_notebook(notebook_path):
    with open(notebook_path, 'r', encoding='utf-8') as f:
        notebook = json.load(f)
    
    for cell in notebook['cells']:
        if 'outputs' in cell:
            cell['outputs'] = []
        if 'execution_count' in cell:
            cell['execution_count'] = None
        if 'metadata' in cell:
            # Remove execution-related metadata
            if 'execution' in cell['metadata']:
                del cell['metadata']['execution']
    
    with open(notebook_path, 'w', encoding='utf-8') as f:
        json.dump(notebook, f, indent=2, ensure_ascii=False)

if __name__ == "__main__":
    if len(sys.argv) > 1:
        clean_notebook(sys.argv[1])
        print(f"Cleaned {sys.argv[1]}")
    else:
        print("Usage: python clean_notebook.py <notebook_path.ipynb>")
```

### 3. Using nbstripout (Third-party tool)
```bash
# Install nbstripout first
pip install nbstripout

# Clean single file
nbstripout notebook.ipynb

# Clean all files in directory
find . -name "*.ipynb" -exec nbstripout {} \;
```

## Usage Examples

1. **Clean specific notebook**:
   ```bash
   jupyter nbconvert --ClearOutputPreprocessor.enabled=True --inplace /mnt/d/forCoding_code/QuantFinance/plan_3-standardization_1/3.0-runner.ipynb
   ```

2. **Clean all notebooks in project**:
   ```bash
   find /mnt/d/forCoding_code/QuantFinance -name "*.ipynb" -exec jupyter nbconvert --ClearOutputPreprocessor.enabled=True --inplace {} \;
   ```

3. **Backup and clean**:
   ```bash
   # Backup first
   cp /path/to/notebook.ipynb /path/to/notebook.ipynb.backup
   # Then clean
   jupyter nbconvert --ClearOutputPreprocessor.enabled=True --inplace /path/to/notebook.ipynb
   ```

## Notes

- The `--inplace` flag modifies the file directly
- Always make backups before cleaning important notebooks
- This process preserves code, markdown, and cell structure
- Removes: outputs, execution counts, and execution metadata
- Keeps: code content, markdown, cell order, and non-execution metadata