#!/usr/bin/env python3
import json
import re

# Read the authors.json file
with open('bookey_scraper/scrapped_data/authors.json', 'r') as f:
    authors = json.load(f)

# Read the current seed_authors.go file
with open('internal/seed/seed_authors.go', 'r') as f:
    content = f.read()

# Find the position before the final fmt.Println statement
insert_pos = content.rfind('fmt.Println("authors seeded")')

# Generate the author entries
author_entries = []
for author in authors:
    name = author['name'].strip()
    info = author['info'].strip()
    
    # Clean up the info text - replace newlines with spaces and escape quotes
    info = re.sub(r'\s+', ' ', info)
    info = info.replace('"', '\\"')
    
    entry = f'\tauthorsStore.CreateAuthor(ctx, "{name}", `{info}`)'
    author_entries.append(entry)

# Insert the new authors before the final statement
new_content = content[:insert_pos] + '\n\n\t// Additional authors from authors.json\n' + '\n\n'.join(author_entries) + '\n\n' + content[insert_pos:]

# Write the updated file
with open('internal/seed/seed_authors.go', 'w') as f:
    f.write(new_content)

print(f'Successfully added {len(authors)} authors to seed_authors.go') 