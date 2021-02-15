<p align="center">
    <a href="https://github.com/Cobertos/notion_export_enhancer/actions" target="_blank"><img alt="build status" src="https://github.com/Cobertos/notion_export_enhancer/workflows/Package%20Tests/badge.svg"></a>
    <a href="https://pypi.org/project/notion_export_enhancer/" target="_blank"><img alt="pypi python versions" src="https://img.shields.io/pypi/pyversions/notion_export_enhancer.svg"></a>
    <a href="https://twitter.com/cobertos" target="_blank"><img alt="twitter" src="https://img.shields.io/badge/twitter-%40cobertos-0084b4.svg"></a>
    <a href="https://cobertos.com" target="_blank"><img alt="twitter" src="https://img.shields.io/badge/website-cobertos.com-888888.svg"></a>
</p>

# Notion Export Enhancer

Takes a [Notion.so](https://notion.so) export .zip and enhances it by:

* Removing all Notion IDs from the end of folders and files
* Adds Unicode Emoji to start of folder/file names if it was in your Notion notes
* Retruncates note titles to 200 characters instead of 50
* Applies Notion's modification time to the file data itself
* Moves root md files into the folder with their name, giving them a name like `!index.md` instead so they sort to the top.

<p align="center">
    <img alt="folders with emojis" src="https://raw.githubusercontent.com/Cobertos/notion_export_enhancer/owo/media/folders.png">
</p>

TODO:
* Remove empty notes (ones with only links)?
* Rewrite csv + md tables into md tables where appropriate?
* .exe instead of .py?
* Image captions should become MD alt image text, not a separate paragraph
  * Would require exporting everything ourselves, paragraph after image is ambiguous

Supports Python 3.6+

## Usage from CLI

* Export your notion workspace
  * You can export a single workspace from `Settings > [Workspace] Settings > Export Content > Export all workspace content`

<p align="center">
    <img alt="Notion export menu for where to export workspace" src="https://raw.githubusercontent.com/Cobertos/notion_export_enhancer/owo/media/where-to-export.png">
</p>

  * Choose export option `"Markdown & CSV"`
* `pip install notion_export_enhancer`
* Then run like `python -m notion_export_enhancer [token_v2] [path_to_zip]`
  * `token_v2` is your Notion.so token, which can be obtained by inspecting your browser cookies on a logged-in (non-guest) session on Notion.so

There are also some configuration options:

* `--output-path`: Optionally set an output path, otherwise uses the current working directory
* `--remove-title`: Removes the title that Notion adds. H1s at the top of every file (default false)
* `--rewrite-paths`: Rewrite the paths in the Markdown files themselves to match file renaming (default true)

## Contributing
See [CONTRIBUTING.md](https://github.com/Cobertos/notion_export_enhancer/blob/master/CONTRIBUTING.md)
