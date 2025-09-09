#!/usr/bin/env python3
import json
import html
from markdownify import markdownify as md
from typing import Dict, List
import re

def clean_html_entities(text: str) -> str:
    """Decode HTML entities like &amp; &lt; &gt; etc."""
    if not text:
        return text
    
    # First unescape HTML entities
    text = html.unescape(text)
    
    # Common HTML entities that might be double-encoded
    replacements = {
        '&amp;': '&',
        '&lt;': '<',
        '&gt;': '>',
        '&quot;': '"',
        '&#039;': "'",
        '&nbsp;': ' ',
        '&ldquo;': '"',
        '&rdquo;': '"',
        '&lsquo;': "'",
        '&rsquo;': "'",
        '&mdash;': '—',
        '&ndash;': '–',
        '&hellip;': '…',
    }
    
    for entity, char in replacements.items():
        text = text.replace(entity, char)
    
    return text

def html_to_markdown(html_content: str) -> str:
    """Convert HTML to clean markdown text."""
    if not html_content:
        return ""
    
    # First clean HTML entities
    html_content = clean_html_entities(html_content)
    
    # Convert to markdown
    # strip=['img'] removes image tags, you can add more tags to strip if needed
    markdown_text = md(html_content, 
                       heading_style="ATX",  # Use # for headings
                       bullets="-",  # Use - for bullet lists
                       strip=['script', 'style', 'meta', 'link'],  # Remove these tags completely
                       escape_asterisks=False,  # Don't escape asterisks
                       escape_underscores=False)  # Don't escape underscores
    
    # Clean up excessive whitespace
    markdown_text = re.sub(r'\n{3,}', '\n\n', markdown_text)  # Max 2 newlines
    markdown_text = re.sub(r' +', ' ', markdown_text)  # Multiple spaces to single
    markdown_text = re.sub(r'\n +', '\n', markdown_text)  # Remove leading spaces on lines
    
    # Remove any remaining HTML comments
    markdown_text = re.sub(r'<!--.*?-->', '', markdown_text, flags=re.DOTALL)
    
    # Strip leading/trailing whitespace
    markdown_text = markdown_text.strip()
    
    return markdown_text

def clean_articles(input_file: str, output_file: str):
    """Process articles JSON file and convert HTML to markdown."""
    
    print(f"Loading articles from {input_file}...")
    with open(input_file, 'r', encoding='utf-8') as f:
        articles = json.load(f)
    
    print(f"Processing {len(articles)} articles...")
    
    cleaned_articles = []
    processed = 0
    
    for article in articles:
        # Create cleaned article
        cleaned_article = {
            'id': article.get('id'),
            'title': clean_html_entities(article.get('title', '')),
            'content': html_to_markdown(article.get('content', '')),
            'category': article.get('category'),
            'category_slug': article.get('category_slug'),
            'author_id': article.get('author_id'),
            'published_time': article.get('published_time'),
            'created_time': article.get('created_time'),
            'updated_time': article.get('updated_time'),
            'slug': article.get('slug'),
            'tags': article.get('tags'),
            'source': article.get('source'),
            'language': article.get('language'),
            'view_count': article.get('view_count')
        }
        
        # Clean preview if it exists
        if 'preview' in article and article['preview']:
            cleaned_article['preview'] = html_to_markdown(article['preview'])
        
        # Clean caption if it exists
        if 'caption' in article and article['caption']:
            cleaned_caption = clean_html_entities(article['caption'])
            # Only add if not empty after cleaning
            if cleaned_caption.strip():
                cleaned_article['caption'] = cleaned_caption
        
        cleaned_articles.append(cleaned_article)
        
        processed += 1
        if processed % 1000 == 0:
            print(f"  Processed {processed} articles...")
    
    print(f"Writing cleaned articles to {output_file}...")
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(cleaned_articles, f, ensure_ascii=False, indent=2, default=str)
    
    print(f"Successfully cleaned {len(cleaned_articles)} articles")
    
    # Print statistics
    articles_with_content = sum(1 for a in cleaned_articles if a.get('content'))
    articles_with_preview = sum(1 for a in cleaned_articles if a.get('preview'))
    articles_with_caption = sum(1 for a in cleaned_articles if a.get('caption'))
    
    print(f"\nStatistics:")
    print(f"- Total articles: {len(cleaned_articles)}")
    print(f"- Articles with content: {articles_with_content}")
    print(f"- Articles with preview: {articles_with_preview}")
    print(f"- Articles with caption: {articles_with_caption}")
    
    # Show sample
    if cleaned_articles and articles_with_content > 0:
        sample = next((a for a in cleaned_articles if a.get('content')), cleaned_articles[0])
        print(f"\nSample cleaned article:")
        print(f"  Title: {sample['title']}")
        print(f"  Category: {sample.get('category', 'N/A')}")
        if sample.get('content'):
            preview = sample['content'][:200] + '...' if len(sample['content']) > 200 else sample['content']
            print(f"  Content (markdown): {preview}")

def main():
    input_file = 'articles.json'
    output_file = 'articles_clean.json'
    
    try:
        clean_articles(input_file, output_file)
    except FileNotFoundError:
        print(f"Error: {input_file} not found. Please run extract_articles.py first.")
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()