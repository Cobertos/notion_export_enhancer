"""
Takes a [Notion.so](https://notion.so) export .zip and enhances it
"""

import tempfile
import sys
import os
import time
import re
import argparse
import zipfile
import urllib.parse
from datetime import datetime
from pathlib import Path
import backoff
import requests
from emoji_extractor.extract import Extractor as EmojiExtractor
from notion.client import NotionClient
from notion.block import PageBlock

def noteNameRewrite(nCl, originalNameNoExt):
  """
  Takes original name (with no extension) and renames it using the Notion ID
  and data from Notion itself
  * Removes the Notion ID
  * Looks up the Notion ID for it's icon, and appends if we can find it
  """
  match = re.search(r"(.+?) ([0-9a-f]{32})$", originalNameNoExt)
  if not match:
    return (None, None, None)

  notionId = match[2]

  # Query notion for the ID
  #print(f"Fetching Notion ID '{notionId}' for '{originalNameNoExt}'")
  try:
    pageBlock = nCl.get_block(notionId)
  except requests.exceptions.HTTPError:
    print(f"Failed to retrieve ID {notionId}")
    return (None, None, None)

  # The ID might not be a PageBlock (like when a note with no child PageBlocks
  # has an image in it, generating a folder, Notion uses the ID of the first
  # ImageBlock, maybe a bug on Notion's end? lol)
  if not isinstance(pageBlock, PageBlock):
    print(f"Block at ID {notionId}, was not PageBlock. Was {type(pageBlock).__name__}")
    if hasattr(pageBlock, 'parent') and pageBlock.parent is not None:
      # Try traversing up the parents for the first page
      while hasattr(pageBlock, 'parent') and not isinstance(pageBlock, PageBlock):
        pageBlock = pageBlock.parent
      if isinstance(pageBlock, PageBlock):
        print(f"Using some .parent as PageBlock")
    elif hasattr(pageBlock, 'children') and pageBlock.children is not None:
      # Try to find a PageBlock in the children, but only use if one single one exists
      pageBlockChildren = [c for c in pageBlock.children if isinstance(c, PageBlock)]
      if len(pageBlockChildren) != 1:
        print(f"Ambiguous .children, contained {len(pageBlockChildren)} chlidren PageBlocks")
      else:
        print(f"Using .children[0] as PageBlock")
        pageBlock = pageBlockChildren[0]

  if not isinstance(pageBlock, PageBlock):
    print(f"Failed to retrieve PageBlock for ID {notionId}")
    return (None, None, None)

  
    #print(f"Found parent '{type(pageBlock).__name__}' instead")

  # Check for name truncation
  newName = match[1]
  if len(match[1]) == 50:
    # Use full name instead, invalids replaced with " ", like the normal export
    # TODO: These are just Windows reserved characters
    # TODO: 200 was just a value to stop Windows from complaining
    newName = re.sub(r"[\\/?:*\"<>|]", " ", pageBlock.title)
    if len(newName) > 200:
      print(f"'{newName}' too long, truncating to 200")
      newName = newName[0:200]

  # Add icon to the front if it's there and usable
  icon = pageBlock.icon
  if icon and EmojiExtractor().big_regex.match(icon): # A full match of a single emoji, might be None or an https://aws.amazon uploaded icon
    newName = f"{icon} {newName}"

  # Also get the times to set the file to
  createdTime = datetime.fromtimestamp(int(pageBlock._get_record_data()["created_time"])/1000)
  lastEditedTime = datetime.fromtimestamp(int(pageBlock._get_record_data()["last_edited_time"])/1000)

  return (newName, createdTime, lastEditedTime)

class NotionExportRenamer:
  """
  Holds state information for renaming a single Notion.so export. Allows it to avoid
  naming collisions and store other state
  """
  def __init__(self, notionClient, rootPath):
    self.notionClient = notionClient
    self.rootPath = rootPath
    # Dict containing all the paths we've renamed and what they were renamed to
    # (plus createdtime and lastEditedTime). Strings with relative directories to
    # rootPath mapped to 3 tuples returned from noteNameRewrite
    self._renameCache = {}
    # Dict containing keys where it is an unrenamed path with the last part being
    # renamed mapped to True. Used to see if other files in the folder might
    # have the same name and to act accordingly
    self._collisionCache = {}

  def renameAndTimesWithNotion(self, pathToRename):
    """
    Takes an original on file-system path and rewrites _just the basename_. It
    collects rename operations for speed and collision prevention (as some renames
    will cause the same name to occur)
    @param {string} realPath The path to rename the basename of. Must point to an
    actual unrenamed file/folder on disk rooted at self.rootPath so we can scan around it
    @returns {tuple} 3 tuple of new name, created time and modified time
    """
    if pathToRename in self._renameCache:
      return self._renameCache[pathToRename]

    path, name = os.path.split(pathToRename)
    nameNoExt, ext = os.path.splitext(name)
    newNameNoExt, createdTime, lastEditedTime = noteNameRewrite(self.notionClient, nameNoExt)
    if not newNameNoExt: # No rename happened, probably no ID in the name or not an .md file
      self._renameCache[pathToRename] = (name, None, None)
    else:
      # Merge files into folders in path at same name if that folder exists
      if ext == '.md':
        p = Path(os.path.join(self.rootPath, path, nameNoExt))
        if p.exists() and p.is_dir():
          # NOTE: newNameNoExt can contain a '/' for path joining later!
          newNameNoExt = os.path.join(newNameNoExt, "!index")

      # Check to see if name collides
      if os.path.join(path, newNameNoExt) in self._collisionCache:
        # If it does, try progressive (i) until a new one is found
        i = 1
        collidingNameNoExt = newNameNoExt
        while os.path.join(path, newNameNoExt) in self._collisionCache:
          newNameNoExt = f"{collidingNameNoExt} ({i})"
          i += 1

      self._renameCache[pathToRename] = (f"{newNameNoExt}{ext}", createdTime, lastEditedTime)
      self._collisionCache[os.path.join(path, newNameNoExt)] = True

    return self._renameCache[pathToRename]

  def renameWithNotion(self, pathToRename):
    """
    Takes an original on file-system path and rewrites _just the basename_. It
    collects rename operations for speed and collision prevention (as some renames
    will cause the same name to occur)
    @param {string} pathToRename The path to rename the basename of. Must point to an
    actual unrenamed file/folder on disk rooted at self.rootPath so we can scan around it
    @returns {string} The new name
    """
    return self.renameAndTimesWithNotion(pathToRename)[0]

  def renamePathWithNotion(self, pathToRename):
    """
    Renames all parts of a path
    @param {string} pathToRename A real path on disk to a file or folder root at
    self.rootPath. All pieces of the path will be renamed
    """
    pathToRenameSplit = re.split(r"[\\/]", pathToRename)
    paths = [os.path.join(*pathToRenameSplit[0:rpc + 1]) for rpc in range(len(pathToRenameSplit))]
    return os.path.join(*[self.renameWithNotion(rp) for rp in paths])

  def renamePathAndTimesWithNotion(self, pathToRename):
    """
    Renames all parts of a path and return the created and lastEditedTime for the last
    part of the path (the file)
    @param {string} pathToRename A real path on disk to a file or folder root at
    self.rootPath. All pieces of the path will be renamed
    """
    newPath = self.renamePathWithNotion(os.path.dirname(pathToRename))
    newName, createdTime, lastEditedTime = self.renameAndTimesWithNotion(pathToRename)
    return (os.path.join(newPath, newName), createdTime, lastEditedTime)

def mdFileRewrite(renamer, mdFilePath, mdFileContents=None, removeTopH1=False, rewritePaths=False):
  """
  Takes a Notion exported md file and rewrites parts of it
  @param {string} mdFilePath String to the markdown file that's being editted, rooted at
  self.rootPath
  @param {string} [mdFileContents=None] The contents of the markdown file, if not provided
  we will read it manually
  @param {boolean} [removeTopH1=False] Remove the title on the first line of the MD file?
  @param {boolean} [rewritePaths=False] Rewrite the relative paths in the MD file (images and links)
  using Notion file name rewriting
  """
  if not mdFileContents:
    raise NotImplementedError("TODO: Not passing mdFileContents is not implemented... please pass it ;w;")

  newMDFileContents = mdFileContents
  if removeTopH1:
    lines = mdFileContents.split("\n")
    newMDFileContents = "\n".join(lines[1:])

  if rewritePaths:
    # Notion link/images use relative paths to other notes, which we can't known without
    # consulting the file tree and renaming (to handle duplicates and such)
    # Notion links are also URL encoded
    # Can't use finditer because we modify the string each time...
    searchStartIndex = 0
    while True:
      m = re.search(r"!?\[.+?\]\(([\w\d\-._~:/?=#%\]\[@!$&'\(\)*+,;]+?)\)", newMDFileContents[searchStartIndex:])
      if not m:
        break

      if re.search(r":/", m.group(1)):
        searchStartIndex = searchStartIndex + m.end(1)
        continue # Not a local file path
      relTargetFilePath = urllib.parse.unquote(m.group(1))

      # Convert the current MD file path and link target path to the renamed version
      # (also taking into account potentially mdFilePath renames moving the directory)
      mdDirPath = os.path.dirname(mdFilePath)
      newTargetFilePath = renamer.renamePathWithNotion(os.path.join(mdDirPath, relTargetFilePath))
      newMDDirPath = os.path.dirname(renamer.renamePathWithNotion(mdFilePath))
      # Find the relative path to the newly converted paths for both files
      newRelTargetFilePath = os.path.relpath(newTargetFilePath, newMDDirPath)
      # Convert back to the way markdown expects the link to be
      newRelTargetFilePath = re.sub(r"\\", "/", newRelTargetFilePath)
      newRelTargetFilePath = urllib.parse.quote(newRelTargetFilePath)

      # Replace the path in the original string with the new relative renamed
      # target path
      newMDFileContents = newMDFileContents[0:m.start(1) + searchStartIndex] + newRelTargetFilePath + newMDFileContents[m.end(1) + searchStartIndex:]
      searchStartIndex = searchStartIndex + m.start(1) + len(newRelTargetFilePath)

  return newMDFileContents

def rewriteNotionZip(notionClient, zipPath, outputPath=".", removeTopH1=False, rewritePaths=True):
  """
  Takes a Notion .zip and prettifies the whole thing
  * Removes all Notion IDs from end of names, folders and files
  * Add icon to the start of folder/file name if Unicode character
  * For files had content in Notion, move them inside the folder, and set the
    name to something that will sort to the top
  * Fix links inside of files
  * Optionally remove titles at the tops of files

  @param {NotionClient} notionClient The NotionClient to use to query Notion with
  @param {string} zipPath The path to the Notion zip
  @param {string} [outputPath="."] Optional output path, otherwise will use cwd
  @param {boolean} [removeTopH1=False] To remove titles at the top of all the md files
  @param {boolean} [rewritePaths=True] To rewrite all the links and images in the Markdown files too
  @returns {string} Path to the output zip file
  """
  with tempfile.TemporaryDirectory() as tmpDir:
    # Unpack the whole thing first (probably faster than traversing it zipped, like with tar files)
    print(f"Extracting '{zipPath}' temporarily...")
    with zipfile.ZipFile(zipPath) as zf:
      zf.extractall(tmpDir)

    # Make new zip to begin filling
    zipName = os.path.basename(zipPath)
    newZipName = f"{zipName}.formatted"
    newZipPath = os.path.join(outputPath, newZipName)
    with zipfile.ZipFile(newZipPath, 'w', zipfile.ZIP_DEFLATED) as zf:

      #Traverse over the files, renaming, modifying, and rewriting back to the zip
      renamer = NotionExportRenamer(notionClient, tmpDir)
      for tmpWalkDir, dirs, files in os.walk(tmpDir):
        walkDir = os.path.relpath(tmpWalkDir, tmpDir)
        for name in files:
          realPath = os.path.join(tmpWalkDir, name)
          relPath = os.path.join("" if walkDir == "." else walkDir, name) # Prevent paths starting with .\\ which, when written to the tar, do annoying things
          # print(f"Reading '{root}' '{name}'")

          # Rewrite the current path and get the times from Notion
          print("---")
          print(f"Working on '{relPath}'")
          newPath, createdTime, lastEditedTime = renamer.renamePathAndTimesWithNotion(relPath)

          if os.path.splitext(name)[1] == ".md":
            # Grab the data from the file if md file
            with open(realPath, "r", encoding='utf-8') as f:
              mdFileData = f.read()
            mdFileData = mdFileRewrite(renamer, relPath, mdFileContents=mdFileData, removeTopH1=removeTopH1, rewritePaths=rewritePaths)

            print(f"Writing as '{newPath}' with time '{lastEditedTime}'")
            zi = zipfile.ZipInfo(newPath, lastEditedTime.timetuple())
            zf.writestr(zi, mdFileData)
          else:
            print(f"Writing as '{newPath}' with time from original export (not an .md file)")
            zf.write(realPath, newPath)
  return newZipPath


def cli(argv):
  """
  CLI entrypoint, takes CLI arguments array
  """
  parser = argparse.ArgumentParser(description='Prettifies Notion .zip exports')
  parser.add_argument('token_v2', type=str,
                      help='the token for your Notion.so session')
  parser.add_argument('zip_path', type=str,
                      help='the path to the Notion exported .zip file')
  parser.add_argument('--output-path', action='store', type=str, default=".",
                      help='The path to output to, defaults to cwd')
  parser.add_argument('--remove-title', action='store_true',
                      help='Removes the title that Notion adds. H1s at the top of every file')
  parser.add_argument('--rewrite-paths', action='store_false', default=True,
                      help='Rewrite the paths in the Markdown files themselves to match file renaming')
  args = parser.parse_args(argv)

  startTime = time.time()
  nCl = NotionClient(token_v2=args.token_v2)
  nCl.get_block = backoff.on_exception(backoff.expo,
                      requests.exceptions.HTTPError,
                      max_tries=5,
                      )(nCl.get_block)

  outFileName = rewriteNotionZip(nCl, args.zip_path, outputPath=args.output_path,
    removeTopH1=args.remove_title, rewritePaths=args.rewrite_paths)
  print("--- Finished in %s seconds ---" % (time.time() - startTime))
  print(f"Output file written as '{outFileName}'")

if __name__ == "__main__":
  cli(sys.argv[1:])
