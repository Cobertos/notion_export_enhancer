'''
Tests NotionPyRenderer parsing
'''
import pytest
from datetime import datetime
import sys
import os
from notion_export_enhancer.enhancer import noteNameRewrite, renameAndTimesWithNotion, \
    renameWithNotion, renamePathWithNotion
from notion.block import PageBlock
from unittest.mock import Mock

#No-op, seal doesn't exist in Python 3.6
if sys.version_info >= (3,7,0):
    from unittest.mock import seal
else:
    seal = lambda x: x

defaultBlockTimeNotion = "1609238729000"
defaultBlockTime = datetime.fromtimestamp(1609238729)

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



def test_renameAndTimesWithNotion_no_rename():
    '''it will not rename paths that dont match'''
    #arrange
    nCl = MockClient()

    #act
    ret = renameAndTimesWithNotion(nCl, 'a/b/c.png')

    #assert
    assert ret == ('c.png', None, None)

def test_renameAndTimesWithNotion_simple_rename():
    '''it will rename normal paths'''
    #arrange
    nCl = MockClient({
        '0123456789abcdef0123456789abcdef': MockBlock()
    })

    #act
    ret = renameAndTimesWithNotion(nCl, 'a/b/c 0123456789abcdef0123456789abcdef.md')

    #assert
    assert ret == ('c.md', defaultBlockTime, defaultBlockTime)

def test_renameAndTimesWithNotion_rename_collision_handle():
    '''it will rename while handling collisions from previous conversions'''
    #arrange
    nCl = MockClient({
        '0123456789abcdef0123456789abcdef': MockBlock(),
        '00000000000000000000000000000000': MockBlock(),
        '11111111111111111111111111111111': MockBlock(),
    })

    #act
    ret = renameAndTimesWithNotion(nCl, 'a/b/c 0123456789abcdef0123456789abcdef.md')
    ret2 = renameAndTimesWithNotion(nCl, 'a/b/c 00000000000000000000000000000000.md')
    ret3 = renameAndTimesWithNotion(nCl, 'a/b/c 11111111111111111111111111111111.md')

    #assert
    assert ret == ('c.md', defaultBlockTime, defaultBlockTime)
    assert ret2 == ('c (1).md', defaultBlockTime, defaultBlockTime)
    assert ret3 == ('c (2).md', defaultBlockTime, defaultBlockTime)

def test_renameWithNotion_simple_rename():
    '''it will rename if path matches and only return name'''
    #arrange
    nCl = MockClient({
        '0123456789abcdef0123456789abcdef': MockBlock(),
    })

    #act
    ret = renameWithNotion(nCl, 'a/b/c 0123456789abcdef0123456789abcdef.md')

    #assert
    assert ret == 'c.md'

def test_renamePathWithNotion_simple_rename():
    '''it will rename a full path'''
    #arrange
    nCl = MockClient({
        '0123456789abcdef0123456789abcdef': MockBlock(),
        '00000000000000000000000000000000': MockBlock(),
        '11111111111111111111111111111111': MockBlock(),
    })

    #act
    ret = renamePathWithNotion(nCl, \
        'a 11111111111111111111111111111111/b 00000000000000000000000000000000/c 0123456789abcdef0123456789abcdef.md', \
        'a 11111111111111111111111111111111/b 00000000000000000000000000000000/c 0123456789abcdef0123456789abcdef.md')

    #assert
    assert ret == os.path.join('a', 'b', 'c.md')