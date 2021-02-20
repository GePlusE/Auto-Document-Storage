# Auto-Document-Storage
Automatically detects new PDFs in a specific directory, finds or creates the directory for the file, renames it and saves it to the target directory.

### How to:
- Use a prefix separated by "__" (two underscores) infront of a files name as the target directory's name (e.g., "FOLDER__Document Name.pdf"). Ths script will use the prefix automatically as the name of the target directory. 

### Format for credentials.py
```python
directory_to_clean = "path/to/directory"
target_directory = "path/to/target/directory"
types_to_ignore = [".DS_Store"] # append list with your own types which should be ignored
```
