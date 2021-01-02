'''
Tests NotionPyRenderer parsing
'''
import pytest
from datetime import datetime
import sys
import os
import re
import zipfile
from notion_export_enhancer.enhancer import noteNameRewrite, NotionExportRenamer, \
    mdFileRewrite, rewriteNotionZip
from notion.block import PageBlock
from unittest.mock import Mock

#No-op, seal doesn't exist in Python 3.6
if sys.version_info >= (3,7,0):
    from unittest.mock import seal
else:
    seal = lambda x: x

testsRoot = os.path.dirname(os.path.realpath(__file__))
defaultBlockTimeNotion = "7955187742000" #2/2/2222 22:22:22
defaultBlockTime = datetime.fromtimestamp(7955187742)

def MockBlock(title='', icon=None, createdTime=defaultBlockTimeNotion, lastEditedTime=None, spec=PageBlock):
    mockBlock = Mock(spec=spec)
    mockBlock._get_record_data = Mock(return_value={ "created_time": createdTime, "last_edited_time": lastEditedTime or createdTime })
    mockBlock.icon = icon
    mockBlock.title = title
    seal(mockBlock)
    return mockBlock

def MockClient(blockMap={}):
    notionClient = Mock()
    notionClient.return_value = notionClient
    notionClient.get_block = lambda bId: blockMap[bId]
    seal(notionClient)
    return notionClient

def test_noteNameRewrite_non_matching_names():
    '''it will return None tuple when not matching pattern'''
    #arrange
    nCl = MockClient()

    #act/assert
    assert noteNameRewrite(nCl, 'asdf') == (None, None, None)
    assert noteNameRewrite(nCl, 'asdf 4fe9r0ogij') == (None, None, None)

def test_noteNameRewrite_name():
    '''it will return properly extracted name'''
    #arrange
    nCl = MockClient({
        '0123456789abcdef0123456789abcdef': MockBlock()
    })

    #act
    ret = noteNameRewrite(nCl, 'asdf 0123456789abcdef0123456789abcdef')

    #assert
    assert ret == ('asdf', defaultBlockTime, defaultBlockTime)

def test_noteNameRewrite_long_names():
    '''it will retruncate names from Notion'''
    #arrange
    nCl = MockClient({
        '0123456789abcdef0123456789abcdef': MockBlock(title="abcdefghijklmnopqrstuvwxyzabcdefghijklmnopqrstuvwxyz")
    })

    #act
    ret = noteNameRewrite(nCl, 'abcdefghijklmnopqrstuvwxyzabcdefghijklmnopqrstuvwx 0123456789abcdef0123456789abcdef')

    #assert
    assert ret == ('abcdefghijklmnopqrstuvwxyzabcdefghijklmnopqrstuvwxyz', defaultBlockTime, defaultBlockTime)

def test_noteNameRewrite_icon_not_emoji():
    '''it will not use the icon from the block if it's not an emoji'''
    #arrange
    nCl = MockClient({
        '0123456789abcdef0123456789abcdef': MockBlock(icon="https://example.com")
    })

    #act
    ret = noteNameRewrite(nCl, 'owo 0123456789abcdef0123456789abcdef')

    #assert
    assert ret == ('owo', defaultBlockTime, defaultBlockTime)

def test_noteNameRewrite_icon_emoji():
    '''it will not use the icon if it's an emoji, even if multiple unicode characters'''
    #arrange
    nCl = MockClient({
        '0123456789abcdef0123456789abcdef': MockBlock(icon="🌲"), # Single code point
        '00000000000000000000000000000000': MockBlock(icon="🕳️") # Multiple code points "U+1F573, U+FE0F"
    })

    #act
    ret = noteNameRewrite(nCl, 'owo 0123456789abcdef0123456789abcdef')
    ret2 = noteNameRewrite(nCl, 'owo 00000000000000000000000000000000')

    #assert
    assert ret == ('🌲 owo', defaultBlockTime, defaultBlockTime)
    assert ret2 == ('🕳️ owo', defaultBlockTime, defaultBlockTime)

def test_noteNameRewrite_times():
    '''it will get times from Notion as well, as datetime objects'''
    #arrange
    nCl = MockClient({
        '0123456789abcdef0123456789abcdef': MockBlock(createdTime="1555555555000", lastEditedTime="16666666666777")
    })

    #act
    ret = noteNameRewrite(nCl, 'owo 0123456789abcdef0123456789abcdef')

    #assert
    assert ret == ('owo', datetime.fromtimestamp(1555555555), datetime.fromtimestamp(16666666666.777))



def test_NotionExportRewriter_renameAndTimesWithNotion_no_rename():
    '''it will not rename paths that dont match'''
    #arrange
    nCl = MockClient()
    rn = NotionExportRenamer(nCl, "")

    #act
    ret = rn.renameAndTimesWithNotion(os.path.join('a', 'b', 'c.png'))

    #assert
    assert ret == ('c.png', None, None)

def test_NotionExportRewriter_renameAndTimesWithNotion_simple_rename():
    '''it will rename normal paths'''
    #arrange
    nCl = MockClient({
        '0123456789abcdef0123456789abcdef': MockBlock()
    })
    rn = NotionExportRenamer(nCl, "")

    #act
    ret = rn.renameAndTimesWithNotion(os.path.join('a', 'b', 'c 0123456789abcdef0123456789abcdef.md'))

    #assert
    assert ret == ('c.md', defaultBlockTime, defaultBlockTime)

def test_NotionExportRewriter_renameAndTimesWithNotion_merge_handle():
    '''it will rename while handling collisions from previous conversions'''
    #arrange
    nCl = MockClient({
        '0123456789abcdef0123456789abcdef': MockBlock(),
    })
    rn = NotionExportRenamer(nCl, os.path.join(testsRoot, 'test_files', 'merge_handle'))

    #act
    ret = rn.renameAndTimesWithNotion('test 0123456789abcdef0123456789abcdef.md')

    #assert
    assert ret == (os.path.join('test','!index.md'), defaultBlockTime, defaultBlockTime)

def test_NotionExportRewriter_renameAndTimesWithNotion_rename_collision_handle():
    '''it will rename while handling collisions from previous conversions'''
    #arrange
    nCl = MockClient({
        '0123456789abcdef0123456789abcdef': MockBlock(),
        '00000000000000000000000000000000': MockBlock(),
        '11111111111111111111111111111111': MockBlock(),
    })
    rn = NotionExportRenamer(nCl, "")

    #act
    ret = rn.renameAndTimesWithNotion(os.path.join('a', 'b', 'c 0123456789abcdef0123456789abcdef.md'))
    ret2 = rn.renameAndTimesWithNotion(os.path.join('a', 'b', 'c 00000000000000000000000000000000.md'))
    ret3 = rn.renameAndTimesWithNotion(os.path.join('a', 'b', 'c 11111111111111111111111111111111.md'))

    #assert
    assert ret == ('c.md', defaultBlockTime, defaultBlockTime)
    assert ret2 == ('c (1).md', defaultBlockTime, defaultBlockTime)
    assert ret3 == ('c (2).md', defaultBlockTime, defaultBlockTime)

def test_NotionExportRewriter_renameWithNotion_simple_rename():
    '''it will rename if path matches and only return name'''
    #arrange
    nCl = MockClient({
        '0123456789abcdef0123456789abcdef': MockBlock(),
    })
    rn = NotionExportRenamer(nCl, "")

    #act
    ret = rn.renameWithNotion(os.path.join('a', 'b', 'c 0123456789abcdef0123456789abcdef.md'))

    #assert
    assert ret == 'c.md'

def test_NotionExportRewriter_renamePathWithNotion_simple_rename():
    '''it will rename a full path'''
    #arrange
    nCl = MockClient({
        '0123456789abcdef0123456789abcdef': MockBlock(),
        '00000000000000000000000000000000': MockBlock(),
        '11111111111111111111111111111111': MockBlock(),
    })
    rn = NotionExportRenamer(nCl, os.path.join('x', 'y'))

    #act
    ret = rn.renamePathWithNotion( \
        os.path.join('a 11111111111111111111111111111111', 'b 00000000000000000000000000000000', 'c 0123456789abcdef0123456789abcdef.md'))

    #assert
    assert ret == os.path.join('a', 'b', 'c.md')

def test_NotionExportRewriter_renamePathAndTimesWithNotion_simple_rename():
    '''it will rename a full path'''
    #arrange
    nCl = MockClient({
        '0123456789abcdef0123456789abcdef': MockBlock(createdTime="1000000000000", lastEditedTime="1111111111000"),
        '00000000000000000000000000000000': MockBlock(createdTime="1555555555000", lastEditedTime="1666666666000"),
        '11111111111111111111111111111111': MockBlock(createdTime="1555555555000", lastEditedTime="1666666666000"),
    })
    rn = NotionExportRenamer(nCl, os.path.join('x', 'y'))

    #act
    ret = rn.renamePathAndTimesWithNotion( \
        os.path.join('a 11111111111111111111111111111111', 'b 00000000000000000000000000000000', 'c 0123456789abcdef0123456789abcdef.md'))

    #assert
    assert ret == (os.path.join('a', 'b', 'c.md'), datetime.fromtimestamp(1000000000), datetime.fromtimestamp(1111111111))

def test_mdFileRewrite_no_op():
    '''it will do nothing to md files by default'''
    md = """# I'm really good at taking copypastas from reddit and putting them in 

Now, this is a stowy aww about how My wife got fwipped-tuwned upside down And I'd wike to take a minute Just sit wight thewe I'ww teww you how I became the pwince of a town cawwed Bew Aiw In west Phiwadewphia bown and waised On the pwaygwound was whewe I spent most of my days Chiwwin' out maxin' wewaxin' aww coow And aww shootin some b-baww outside of the schoow When a coupwe of guys who wewe up to no good Stawted making twoubwe in my neighbowhood I got in one wittwe fight and my mom got scawed She said 'You'we movin' with youw auntie and uncwe in Bew Aiw'

I begged and pweaded with hew day aftew day But she packed my suit case and sent me on my way She gave me a kiss and then she gave me my ticket. I put my Wawkman on and said, 'I might as weww kick it'.

Fiwst cwass, yo this is bad Dwinking owange juice out of a champagne gwass. Is this what the peopwe of Bew-Aiw wiving wike? Hmmmmm this might be awwight.
"""
    nCl = MockClient()
    rn = NotionExportRenamer(nCl, '')

    #act
    ret = mdFileRewrite(rn, os.path.join('a', 'b', 'c.md'), mdFileContents=md)

    #assert
    assert ret == md

def test_mdFileRewrite_remove_top_h1():
    '''it will remove the top h1 if configured to'''
    md = """# Copypasta

Okay but for real this is not one of those copy-ma-pastas that you people are taking about. Spaghetti
"""
    nCl = MockClient()
    rn = NotionExportRenamer(nCl, '')

    #act
    ret = mdFileRewrite(rn, os.path.join('a', 'b', 'c.md'), mdFileContents=md, removeTopH1=True)

    #assert
    assert ret == """
Okay but for real this is not one of those copy-ma-pastas that you people are taking about. Spaghetti
"""

def test_mdFileRewrite_rewrite_paths():
    '''it will rewrite paths in the markdown if passed'''
    md = """# Things to do with my time

Okay but really, do you think that me writing this was a good use of time?

[not really](https://example.com). But you know what is a good use of my time? Probably going to the grocery store and getting some food.

What do I need? Maybe something [off my grocery list](Grocery%20List%200123456789abcdef0123456789abcdef.md).

And here's another line just for fun
"""
    nCl = MockClient({
        '0123456789abcdef0123456789abcdef': MockBlock(),
    })
    rn = NotionExportRenamer(nCl, '')

    #act
    ret = mdFileRewrite(rn, os.path.join('a', 'b', 'c.md'), mdFileContents=md, rewritePaths=True)

    #assert
    assert ret == """# Things to do with my time

Okay but really, do you think that me writing this was a good use of time?

[not really](https://example.com). But you know what is a good use of my time? Probably going to the grocery store and getting some food.

What do I need? Maybe something [off my grocery list](Grocery%20List.md).

And here's another line just for fun
"""

def test_mdFileRewrite_rewrite_path_complex():
    '''it will rewrite paths in the markdown if passed, but more complex'''
    md = """# Pathssss

[owo](../d%200123456789abcdef0123456789abcdef.md) [ewe](../e%2044444444444444444444444444444444.md)

[uwu](im%2000000000000000000000000000000000/gay%2011111111111111111111111111111111.md)

[vwv](../cute%2022222222222222222222222222222222/girls%2033333333333333333333333333333333.md)
"""
    nCl = MockClient({
        '0123456789abcdef0123456789abcdef': MockBlock(),
        '00000000000000000000000000000000': MockBlock(),
        '11111111111111111111111111111111': MockBlock(),
        '22222222222222222222222222222222': MockBlock(),
        '33333333333333333333333333333333': MockBlock(),
        '44444444444444444444444444444444': MockBlock(),
    })
    rn = NotionExportRenamer(nCl, '')

    #act
    ret = mdFileRewrite(rn, os.path.join('a', 'b', 'c.md'), mdFileContents=md, rewritePaths=True)

    #assert
    assert ret == """# Pathssss

[owo](../d.md) [ewe](../e.md)

[uwu](im/gay.md)

[vwv](../cute/girls.md)
"""

def test_rewriteNotionZip_simple():
    '''it will rewrite an entire zip file (simple, 1 file, 1 id, no special markdown)'''
    nCl = MockClient({
        '0123456789abcdef0123456789abcdef': MockBlock(createdTime="1000000000000", lastEditedTime="1609459200000"), #1/1/2021 12:00:00 AM
    })

    #act
    outputFilePath = rewriteNotionZip(nCl, os.path.join(testsRoot, 'test_files', 'zip_simple.zip'))

    #assert
    with zipfile.ZipFile(outputFilePath) as zf:
        assert zf.testzip() == None
        assert zf.namelist() == ['test.md']
        assert zf.open('test.md').read().decode('utf-8') == "Simple zip test"
        i = zf.getinfo('test.md')
        assert i.date_time == datetime.fromtimestamp(1609459200).timetuple()[0:6]

def test_rewriteNotionZip_complex():
    '''it will rewrite an entire zip file (simple, 1 file, 1 id, no special markdown)'''
    nCl = MockClient({
        '0123456789abcdef0123456789abcdef': MockBlock(lastEditedTime="1609459200000"), #1/1/2021 12:00:00 AM
        '00000000000000000000000000000000': MockBlock(lastEditedTime="1609459200000"), #1/1/2021 12:00:00 AM
        '11111111111111111111111111111111': MockBlock(icon="📟", lastEditedTime="1609459200000"), #1/1/2021 12:00:00 AM
    })

    #act
    outputFilePath = rewriteNotionZip(nCl, os.path.join(testsRoot, 'test_files', 'zip_complex.zip'))

    #assert
    with zipfile.ZipFile(outputFilePath) as zf:
        assert zf.testzip() == None
        assert set(zf.namelist()) == set(['beep/!index.md', 'beep/📟 types.md', 'device.md', 'something_else.csv'])
        assert zf.open('beep/!index.md').read().decode('utf-8') == """# Beep

A tiny little sound
it feels ever so comforting
an impulse and then it's gone
but the effect ripples through your body

[Types](%F0%9F%93%9F%20types.md)"""
        assert zf.open('device.md').read().decode('utf-8') == """You come across a small device
It's covered in ash and debris
The smooth body has faint ridges that trace your palms
Until it gives and it lets out a soft
[_Beep_](beep/%21index.md)"""
        assert zf.open('beep/📟 types.md').read().decode('utf-8') == """# Types of beeps

* Small
* Soft
* Agile

[beep](../device.md)"""