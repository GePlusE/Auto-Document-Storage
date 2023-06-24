# Auto-Document-Storage
Automatically detects new PDFs in a specific directory, finds or creates the directory for the file, renames it and saves it to the target directory.

### How to:
- Use a prefix separated by "__" (two underscores) infront of a files name as the target directory's name (e.g., ```FOLDER__Document Name.pdf```). Ths script will use the prefix automatically as the name of the target directory.
- Use a second prefix spearated by another pair of underscores to change the name of the file (e.g., ```FOLDER__NEWNAME__Documents Name.pdf``` will change to ```YYYY-MM-DD NEWNAME.pdf```). If you do not use a second pair of underscores the script will not change the name of the file, but will add the current date as prefix.
- **[Optional]** Set up a cronjob to run the script automatically (e.g., every hour or with every reboot).
```
# Auto_Docs_Storage every hour
0 * * * * /Users/.../Auto-Document-Storage/Script.py >/dev/null 2>&1


# Auto_Docs_Storage at boot
@reboot /Users/.../Auto-Document-Storage/Script.py >/dev/null 2>&1
```



### Format for credentials.py
```python
directory_to_clean = "path/to/directory"
target_directory = "path/to/target/directory"
types_to_ignore = [".DS_Store", ".dmg", ".zip", ".icloud"] # append list with your own data types which should be ignored
```
