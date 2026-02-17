import logging

logger = logging.getLogger(__name__)

# Global cache for Notion API responses (expires when script stops)
_notion_cache = {}

def _get_cache_key(function_name: str, **kwargs) -> str:
    """Generate a cache key from function name and parameters (excluding client)."""
    sorted_params = sorted(
        (k, str(v)) for k, v in kwargs.items() if k not in ('client', 'notion')
    )
    key = f"{function_name}:" + "|".join(f"{k}={v}" for k, v in sorted_params)
    return key

def get_inner_page_blocks(notion, page_id):
    """
    Fetch all blocks (children) of a Notion page with caching.
    Results are cached globally and expire when the script stops.
    """
    cache_key = _get_cache_key("get_inner_page_blocks", page_id=page_id)
    
    # Check cache
    if cache_key in _notion_cache:
        logger.debug(f"Cache HIT: {cache_key}")
        return _notion_cache[cache_key]
    
    logger.debug(f"Cache MISS: {cache_key} - fetching from Notion API")
    blocks = []
    start_cursor = None

    while True:
        response = notion.blocks.children.list(
            block_id=page_id,
            start_cursor=start_cursor,
            page_size=100
        )
        blocks.extend(response['results'])
        if not response['has_more']:
            break
        start_cursor = response['next_cursor']

    # Store in cache
    _notion_cache[cache_key] = blocks
    logger.debug(f"Cached {len(blocks)} blocks for {cache_key}")
    
    return blocks

def query_pages_filtered(client, data_source_id, filter_dict=None):
    """
    Query pages from a data source with optional filter, with caching.
    Useful for finding specific pages by property (e.g., project by name).
    Results are cached globally and expire when the script stops.
    
    Args:
        client: Notion client
        data_source_id: Data source ID to query
        filter_dict: Optional filter dict (e.g., {"property": "Name", "title": {"equals": "Project Name"}})
    
    Returns:
        Query results dict with 'results' list
    """
    # Create cache key from data_source_id and filter
    filter_key = str(filter_dict) if filter_dict else "no_filter"
    cache_key = _get_cache_key("query_pages_filtered", data_source_id=data_source_id, filter=filter_key)
    
    # Check cache
    if cache_key in _notion_cache:
        logger.debug(f"Cache HIT: {cache_key}")
        return _notion_cache[cache_key]
    
    logger.debug(f"Cache MISS: {cache_key} - fetching from Notion API")
    
    # Make query
    if filter_dict:
        results = client.data_sources.query(
            data_source_id,
            filter=filter_dict
        )
    else:
        results = client.data_sources.query(
            data_source_id
        )
    
    # Store in cache
    _notion_cache[cache_key] = results
    logger.debug(f"Cached query result for {cache_key}: {len(results.get('results', []))} items")
    
    return results

def get_block_plain_text(block):
    """Extract plain text from any Notion block, comment, page, icon, or cover."""
    if not block:
        return ''
    
    _type = block.get('type', '')
    
    # Helper to extract text from rich_text array
    def extract_rich_text(rich_text_array):
        if not rich_text_array:
            return ''
        return ''.join([text_obj.get('plain_text', '') for text_obj in rich_text_array if isinstance(text_obj, dict)])
    
    # Handle direct text block (from rich_text arrays)
    if _type == 'text':
        return block.get('plain_text', '')
    
    # Handle comments (they have rich_text at top level)
    if _type == 'comment' or 'rich_text' in block and 'object' in block and block['object'] == 'comment':
        return extract_rich_text(block.get('rich_text', []))
    
    # Handle page blocks
    if _type == 'page' or ('object' in block and block['object'] == 'page'):
        # Try to get title from properties
        try:
            title_prop = block.get('properties', {}).get('Name', {}).get('title', [])
            if title_prop:
                return extract_rich_text(title_prop)
            # Try other common title properties
            for prop_name in ['title', 'Title', 'Name']:
                prop = block.get('properties', {}).get(prop_name, {})
                if prop.get('title'):
                    return extract_rich_text(prop['title'])
        except:
            pass
        return ''
    
    # Handle icons
    if _type == 'emoji':
        return block.get('emoji', '')
    
    if _type == 'file' or _type == 'external':
        file_info = block.get(_type, {})
        url = file_info.get('url', '')
        return url
    
    # Handle child_page and child_database
    if _type == 'child_page':
        return block.get('child_page', {}).get('title', '')
    
    if _type == 'child_database':
        return block.get('child_database', {}).get('title', '')
    
    # Text-based blocks
    if _type in ['paragraph', 'heading_1', 'heading_2', 'heading_3', 'bulleted_list_item', 
                 'numbered_list_item', 'quote', 'callout', 'toggle', 'to_do']:
        block_content = block.get(_type, {})
        rich_text = block_content.get('rich_text', [])
        text = extract_rich_text(rich_text)
        
        # For callout, include icon
        if _type == 'callout':
            icon = block_content.get('icon', {})
            icon_text = get_block_plain_text(icon) if icon else ''
            text = f"{icon_text} {text}".strip()
        
        return text
    
    # Code blocks
    if _type == 'code':
        code_content = block.get('code', {})
        rich_text = code_content.get('rich_text', [])
        return extract_rich_text(rich_text)
    
    # List blocks (synced blocks, column lists)
    if _type in ['synced_block', 'column_list', 'column']:
        return ''
    
    # Table blocks
    if _type == 'table':
        return ''
    
    if _type == 'table_row':
        cells = block.get('table_row', {}).get('cells', [])
        cell_texts = []
        for cell in cells:
            cell_text = extract_rich_text(cell)
            cell_texts.append(cell_text)
        return ' | '.join(cell_texts)
    
    # Media blocks
    if _type in ['image', 'video', 'file', 'pdf']:
        media_content = block.get(_type, {})
        caption = media_content.get('caption', [])
        caption_text = extract_rich_text(caption)
        if caption_text:
            return caption_text
        # Return URL if no caption
        url = media_content.get('file', {}).get('url') or media_content.get('external', {}).get('url', '')
        return url
    
    # Embed blocks
    if _type in ['embed', 'bookmark', 'link_preview']:
        content = block.get(_type, {})
        # Try to get caption if available
        caption = content.get('caption', [])
        caption_text = extract_rich_text(caption)
        if caption_text:
            return caption_text
        # Return URL if no caption
        url = content.get('url', '')
        return url
    
    # Link to page
    if _type == 'link_to_page':
        page_ref = block.get('link_to_page', {})
        page_type = page_ref.get('type', '')
        if page_type == 'page_id':
            return page_ref.get('page_id', '')
        elif page_type == 'database_id':
            return page_ref.get('database_id', '')
        return ''
    
    # Divider and breadcrumb
    if _type in ['divider', 'breadcrumb']:
        return ''
    
    # Equation blocks
    if _type == 'equation':
        expression = block.get('equation', {}).get('expression', '')
        return expression
    
    # Template blocks
    if _type in ['template', 'synced_block']:
        return ''
    
    # If we have a rich_text field at top level, try to extract it
    if 'rich_text' in block:
        return extract_rich_text(block['rich_text'])
    
    # If nothing matched, log warning
    if _type:
        logger.warning(f"Unsupported block type: {_type}")
    
    return ''

def extract_property_value(prop):
    """Extract plain text value from any Notion property."""
    if not prop or not isinstance(prop, dict):
        return None
    
    prop_type = prop.get('type')
    
    if prop_type == 'title':
        title_array = prop.get('title', [])
        return ''.join([t.get('plain_text', '') for t in title_array if isinstance(t, dict)])
    
    elif prop_type == 'rich_text':
        rich_text_array = prop.get('rich_text', [])
        return ''.join([t.get('plain_text', '') for t in rich_text_array if isinstance(t, dict)])
    
    elif prop_type == 'number':
        return prop.get('number')
    
    elif prop_type == 'select':
        select_obj = prop.get('select')
        return select_obj.get('name') if select_obj else None
    
    elif prop_type == 'multi_select':
        multi_select_array = prop.get('multi_select', [])
        return [item.get('name') for item in multi_select_array if isinstance(item, dict)]
    
    elif prop_type == 'date':
        date_obj = prop.get('date')
        if not date_obj:
            return None
        start = date_obj.get('start')
        end = date_obj.get('end')
        return {'start': start, 'end': end} if end else start
    
    elif prop_type == 'people':
        people_array = prop.get('people', [])
        return [person.get('name', person.get('id')) for person in people_array]
    
    elif prop_type == 'files':
        files_array = prop.get('files', [])
        return [f.get('name', f.get('file', {}).get('url', '')) for f in files_array]
    
    elif prop_type == 'checkbox':
        return prop.get('checkbox', False)
    
    elif prop_type == 'url':
        return prop.get('url')
    
    elif prop_type == 'email':
        return prop.get('email')
    
    elif prop_type == 'phone_number':
        return prop.get('phone_number')
    
    elif prop_type == 'formula':
        formula_obj = prop.get('formula', {})
        formula_type = formula_obj.get('type')
        return formula_obj.get(formula_type) if formula_type else None
    
    elif prop_type == 'relation':
        relation_array = prop.get('relation', [])
        return [rel.get('id') for rel in relation_array]
    
    elif prop_type == 'rollup':
        rollup_obj = prop.get('rollup', {})
        rollup_type = rollup_obj.get('type')
        return rollup_obj.get(rollup_type) if rollup_type else None
    
    elif prop_type == 'created_time':
        return prop.get('created_time')
    
    elif prop_type == 'created_by':
        created_by = prop.get('created_by', {})
        return created_by.get('name', created_by.get('id'))
    
    elif prop_type == 'last_edited_time':
        return prop.get('last_edited_time')
    
    elif prop_type == 'last_edited_by':
        edited_by = prop.get('last_edited_by', {})
        return edited_by.get('name', edited_by.get('id'))
    
    elif prop_type == 'status':
        status_obj = prop.get('status')
        return status_obj.get('name') if status_obj else None
    
    return None

def get_page_report(notion, page_id):
    page = notion.pages.retrieve(page_id)
    information = {}
    
    page_info = {
        'title': get_block_plain_text(page),
        'cover': get_block_plain_text(page.get('cover', {})),
        'icon': get_block_plain_text(page.get('icon', {}))
    }
    
    # Extract readable property values
    properties = page.get('properties', {})
    properties_extracted = {}
    for prop_name, prop_data in properties.items():
        properties_extracted[prop_name] = {
            'type': prop_data.get('type'),
            'value': extract_property_value(prop_data),
            'raw': prop_data  # Keep raw data for reference
        }
    
    metadata = {
        'id': page['id'],
        'created_time': page['created_time'],
        'last_edited_time': page['last_edited_time'],
        'parent': page['parent'],
        'properties': properties_extracted
    }
    
    comments = notion.comments.list(block_id=page_id)
    comments_texts = [
        get_block_plain_text(c) for c in comments['results']
    ]
    
    children = get_inner_page_blocks(notion, page_id)
    children_tripped = []
    
    for child in children:
        child_data = {
            'id': child['id'],
            'type': child['type'],
            'text': get_block_plain_text(child),
            'has_children': child['has_children'],
            'children': []
        }
        
        # Fetch nested children if they exist
        if child['has_children']:
            try:
                nested_blocks = get_inner_page_blocks(notion, child['id'])
                child_data['children'] = [
                    {
                        'id': nested['id'],
                        'type': nested['type'],
                        'text': get_block_plain_text(nested),
                        'has_children': nested['has_children']
                    }
                    for nested in nested_blocks
                ]
            except Exception as e:
                logger.warning(f"Failed to fetch children for block {child['id']}: {e}")
        
        children_tripped.append(child_data)
    
    information['page_info'] = page_info
    information['metadata'] = metadata
    information['comments'] = comments_texts
    information['children'] = children_tripped
    
    return information

def create_toggle_blocks(text: str, title: str = "Details") -> list[dict]:
    """
    Convert text into Notion-compatible toggle block structure.
    
    Args:
        text: Text content to put inside toggle
        title: Toggle block title
        
    Returns:
        List of Notion block objects
    """
    # Split text into paragraphs
    paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]
    
    # Create children blocks
    children = []
    for para in paragraphs:
        # Check if it's a heading (starts with **)
        if para.startswith('**') and para.count('**') >= 2:
            # Extract heading text
            heading_text = para.split('**')[1]
            children.append({
                "object": "block",
                "type": "heading_3",
                "heading_3": {
                    "rich_text": [{"type": "text", "text": {"content": heading_text}}]
                }
            })
            # Add remaining text as paragraph
            remaining = para.split('**', 2)[2].strip()
            if remaining:
                children.append({
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {
                        "rich_text": [{"type": "text", "text": {"content": remaining}}]
                    }
                })
        else:
            # Regular paragraph
            children.append({
                "object": "block",
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [{"type": "text", "text": {"content": para}}]
                }
            })
    
    # Create toggle block
    toggle_block = {
        "object": "block",
        "type": "toggle",
        "toggle": {
            "rich_text": [{"type": "text", "text": {"content": title}}],
            "children": children
        }
    }
    
    return [toggle_block]
