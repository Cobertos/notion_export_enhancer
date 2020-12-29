import tempfile
import sys
import os
import time
import re
import argparse
import zipfile
from emoji_extractor.extract import Extractor as EmojiExtractor
from datetime import datetime
from pathlib import Path
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
  pageBlock = nCl.get_block(notionId)
  #print(f"Was type '{type(pageBlock).__name__}'")
  # The ID might not be a PageBlock (like when a note with no child PageBlocks
  # has an image in it, generating a folder, Notion uses the ID of the first
  # ImageBlock, maybe a bug on Notion's end? lol)
  while not isinstance(pageBlock, PageBlock):
    pageBlock = pageBlock.parent
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

renameCache = {}
collisionCache = {}
def renameAndTimesWithNotion(nCl, realPath):
  """
  Takes an original on file-system path and rewrites _just the basename_. It
  collects rename operations for speed and collision prevention (as some renames
  will cause the same name to occur)
  @param {NotionClient} nCl The Notion Client to use
  @param {string} realPath The path to rename the basename of
  @returns {tuple} 3 tuple of new name, created time and modified time
  """
  if realPath in renameCache:
    return renameCache[realPath]

  path, name = os.path.split(realPath)
  nameNoExt, ext = os.path.splitext(name)
  newNameNoExt, createdTime, lastEditedTime = noteNameRewrite(nCl, nameNoExt)
  if not newNameNoExt: # No rename happened, probably no ID in the name or not an .md file
    renameCache[realPath] = (name, None, None)
  else:
    # Merge files into folders in path at same name if that folder exists
    if ext == '.md':
      p = Path(os.path.join(path, nameNoExt))
      print(f"Testing path '{os.path.join(path, nameNoExt)}'")
      if p.exists() and p.is_dir():
        # NOTE: newNameNoExt can contain a '/' for path joining later!
        newNameNoExt = os.path.join(newNameNoExt, "!index")

    # Check to see if name collides
    if os.path.join(path, newNameNoExt) in collisionCache:
      # If it does, try progressive (i) until a new one is found
      i = 1
      collidingNameNoExt = newNameNoExt
      while os.path.join(path, newNameNoExt) in collisionCache:
        newNameNoExt = f"{collidingNameNoExt} ({i})"
        i += 1

    renameCache[realPath] = (f"{newNameNoExt}{ext}", createdTime, lastEditedTime)
    collisionCache[os.path.join(path, newNameNoExt)] = True

  return renameCache[realPath]

def renameWithNotion(nCl, realPath):
  """
  Takes an original on file-system path and rewrites _just the basename_. It
  collects rename operations for speed and collision prevention (as some renames
  will cause the same name to occur)
  @param {NotionClient} nCl The Notion Client to use
  @param {string} realPath The path to rename the basename of
  @returns {string} The new name
  """
  return renameAndTimesWithNotion(nCl, realPath)[0]

def renamePathWithNotion(nCl, realPath, pathToRename):
  """
  Renames each part of a path, recursively
  @param {NotionClient} nCl The Notion Client to use
  @param {string} realPath The path _on disk_ pointing to path
  @param {string} path A relative path to rename the parts of only
  """
  if pathToRename == '' or pathToRename == '.':
    return '' # os.path.join('', 'a') returns 'a'

  pathToRenameParent = os.path.dirname(pathToRename)
  realPathParent = os.path.dirname(realPath)
  return os.path.join(renamePathWithNotion(nCl, realPathParent, pathToRenameParent), renameWithNotion(nCl, realPath))


def rewriteNotionZip(notionToken, zipPath, outputPath="."):
  """
  Takes a Notion .zip and prettifies the whole thing
  * Removes all Notion IDs from end of names, folders and files
  * Add icon to the start of folder/file name if Unicode character
  * For files had content in Notion, move them inside the folder, and set the
    name to something that will sort to the top
  * Fix links inside of files

  TODO: Maybe?
  * Remove empty notes (ones with only links)?
  * Remove title at the top of notes?
  @param {string} packagePath The path to the Notion zip
  @param {string} [outputPath=""] Optional output path, otherwise will use cwd
  """
  #print(notionToken, zipPath, outputPath);
  cl = NotionClient(token_v2=notionToken)

  with tempfile.TemporaryDirectory() as tmpDir:
    # Unpack the whole thing first (probably faster than traversing it zipped, like with tar files)
    print(f"Extracting '{zipPath}' temporarily...")
    with zipfile.ZipFile(zipPath) as zf:
      zf.extractall(tmpDir)

    # Make new zip to begin filling
    zipName = os.path.basename(zipPath)
    newZipName = f"{zipName}.formatted"
    with zipfile.ZipFile(os.path.join(outputPath, newZipName), 'w', zipfile.ZIP_DEFLATED) as zf:

      #Traverse over the files, renaming, modifying, and rewriting back to the zip
      for root, dirs, files in os.walk(tmpDir):
        relRoot = os.path.relpath(root, tmpDir)
        for name in files:
          # print(f"Reading '{root}' '{name}'")
          newPath = renamePathWithNotion(cl, root, relRoot)
          newName, createdTime, lastEditedTime = renameAndTimesWithNotion(cl, os.path.join(root, name))
          newPathName = os.path.join(newPath, newName)

          # print(newPath)
          # print(newName)
          # print(createdTime)
          # print(lastEditedTime)

          if os.path.splitext(name)[1] == ".md":
            # Grab the data from the file if md file
            with open(os.path.join(root, name), "r", encoding='utf-8') as f:
              mdFileData = f.read()
            
            # TODO:
            # Rewrite all the links in the file itself, rename using same renaming
            # algorithm
            # s = re.sub(r"^\[([\w\s\d]+)\]\(((?:\/|https?:\/\/)[\w\d./?=#]+)\)$", r"", s)

            print(f"Writing '{newName}' with time '{lastEditedTime}' renamed from '{name}'")
            zi = zipfile.ZipInfo(newPathName, lastEditedTime.timetuple())
            zf.writestr(zi, mdFileData)
          else:
            print(f"Writing '{newName}'")
            zf.write(os.path.join(root, name), newPathName)


def cli(argv):
  parser = argparse.ArgumentParser(description='Prettifies Notion .zip exports')
  parser.add_argument('token_v2', type=str,
                      help='the token for your Notion.so session')
  parser.add_argument('zip_path', type=str,
                      help='the path to the Notion exported .zip file')
  parser.add_argument('--output-path', action='store', type=str, default=".",
                      help='The path to output to, defaults to cwd')
  args = parser.parse_args(argv)

  startTime = time.time()
  rewriteNotionZip(args.token_v2, args.zip_path, args.output_path)
  print("--- Finished in %s seconds ---" % (time.time() - startTime))

if __name__ == "__main__":
  cli(sys.argv[1:])