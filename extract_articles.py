#!/usr/bin/env python3
import argparse
import json
import sys
from typing import Dict, List, Optional


def parse_sql_values_line_by_line(sql_file: str, table_name: str) -> List[List]:
    """Parse SQL INSERT statements line by line for better memory management."""
    values = []

    with open(sql_file, "r", encoding="utf-8") as f:
        in_target_insert = False
        current_row = []
        current_value = ""
        in_quotes = False
        paren_depth = 0
        escape_next = False

        for line in f:
            # Check if we're starting an INSERT for our target table
            if f"INSERT INTO `{table_name}`" in line:
                in_target_insert = True
                # Skip to VALUES part
                if "VALUES" in line:
                    line = line[line.index("VALUES") + 6 :]
                else:
                    continue

            # Skip if we're not in the right INSERT block
            if not in_target_insert:
                continue

            # Check for end of INSERT block (new CREATE or INSERT statement)
            if line.startswith("CREATE TABLE") or (
                line.startswith("INSERT INTO") and table_name not in line
            ):
                in_target_insert = False
                # Process any remaining data
                if current_value:
                    current_row.append(clean_value(current_value))
                if current_row:
                    values.append(current_row)
                break

            # Parse the line character by character
            for char in line:
                if escape_next:
                    current_value += char
                    escape_next = False
                    continue

                if char == "\\" and in_quotes:
                    current_value += char
                    escape_next = True
                    continue

                if char == "'" and not escape_next:
                    in_quotes = not in_quotes
                    current_value += char
                elif char == "(" and not in_quotes:
                    paren_depth += 1
                    if paren_depth == 1:
                        # Start of a new row
                        current_row = []
                        current_value = ""
                elif char == ")" and not in_quotes:
                    paren_depth -= 1
                    if paren_depth == 0:
                        # End of row
                        if current_value:
                            current_row.append(clean_value(current_value))
                        if current_row:
                            values.append(current_row)
                        current_row = []
                        current_value = ""
                elif char == "," and not in_quotes and paren_depth == 1:
                    # End of a value
                    current_row.append(clean_value(current_value))
                    current_value = ""
                elif char == ";" and not in_quotes and paren_depth == 0:
                    # End of INSERT statement
                    in_target_insert = False
                    break
                else:
                    current_value += char

    return values


def clean_value(val: str) -> any:
    """Clean and convert SQL value to Python type."""
    val = val.strip()

    if val == "NULL":
        return None
    elif val.startswith("'") and val.endswith("'"):
        # String value - remove quotes and unescape
        val = val[1:-1]
        val = val.replace("\\'", "'")
        val = val.replace("\\\\", "\\")
        val = val.replace("\\n", "\n")
        val = val.replace("\\r", "\r")
        val = val.replace("\\t", "\t")
        return val
    else:
        # Try to convert to number
        try:
            if "." in val:
                return float(val)
            return int(val)
        except:
            return val


def extract_articles_from_sql(sql_file: str) -> List[Dict]:
    """Extract article information from SQL dump file."""

    posts = {}
    post_contents = {}
    post_categories = {}
    articles = []

    print("Reading SQL file...")

    # Parse categories
    print("Parsing categories...")
    cat_values = parse_sql_values_line_by_line(sql_file, "post_categories")
    for val in cat_values:
        if len(val) >= 14:
            category_id = val[0]
            post_categories[category_id] = {
                "id": category_id,
                "name": val[1],
                "slug": val[2],
                "description": val[3],
                "parent_id": val[5],
            }
    print(f"  Found {len(post_categories)} categories")

    # Parse posts
    print("Parsing posts...")
    posts_values = parse_sql_values_line_by_line(sql_file, "posts")
    for val in posts_values:
        if len(val) >= 23:
            post_id = val[0]
            posts[post_id] = {
                "id": post_id,
                "code": val[1],
                "title": val[3],
                "slug": val[4],
                "preview": val[5],
                "category_id": val[13],
                "author_id": val[17],
                "editor_id": val[18],
                "published_at": val[19],
                "created_at": val[21],
                "updated_at": val[22],
                "tags": val[10],
                "source": val[15],
                "lang": val[9],
                "status": val[7],
                "visibility": val[8],
                "view_count": val[11],
            }
    print(f"  Found {len(posts)} posts")

    # Parse post contents
    print("Parsing post contents...")
    contents_values = parse_sql_values_line_by_line(sql_file, "post_contents")
    for val in contents_values:
        if len(val) >= 7:
            post_id = val[1]
            if post_id not in post_contents:
                post_contents[post_id] = []

            post_contents[post_id].append(
                {
                    "page": val[5] if val[5] else 1,
                    "caption": val[3],
                    "content": val[4],
                    "image": val[2],
                }
            )
    print(f"  Found content for {len(post_contents)} posts")

    print("Combining data into articles...")
    # Combine posts with their contents and categories
    for post_id, post in posts.items():
        # Get category information
        category_name = None
        category_slug = None
        if post["category_id"] in post_categories:
            category = post_categories[post["category_id"]]
            category_name = category["name"]
            category_slug = category["slug"]

        # Combine all content pages into single content field
        combined_content = ""
        combined_caption = ""

        if post_id in post_contents:
            # Sort by page number
            sorted_contents = sorted(post_contents[post_id], key=lambda x: x["page"])

            # Combine captions and content
            captions = []
            contents = []

            for content_page in sorted_contents:
                if content_page["caption"]:
                    captions.append(content_page["caption"])
                if content_page["content"]:
                    contents.append(content_page["content"])

            combined_caption = " ".join(captions) if captions else ""
            combined_content = "\n\n".join(contents) if contents else ""

        # Create unified article record
        article = {
            "title": post["title"],
            "content": combined_content,
            "category": category_name,
            "category_slug": category_slug,
            "author_id": post["author_id"],
            "published_time": post["published_at"],
            "created_time": post["created_at"],
            "updated_time": post["updated_at"],
            "id": post["id"],
            "slug": post["slug"],
            "preview": post["preview"],
            "tags": post["tags"],
            "source": post["source"],
            "language": post["lang"],
            "view_count": post["view_count"],
        }

        # Only add caption if it's not empty
        if combined_caption:
            article["caption"] = combined_caption

        articles.append(article)

    # Sort by published date (newest first)
    articles.sort(
        key=lambda x: x["published_time"] if x["published_time"] else "", reverse=True
    )

    return articles


def main():
    parser = argparse.ArgumentParser(
        description="Extract articles from SQL dump and convert to JSON format",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Extract with default files
  python extract_articles.py
  
  # Specify input and output files
  python extract_articles.py --input-file articles.sql --output-file articles.json
  
  # Extract with filtering options
  python extract_articles.py --input-file dump.sql --output-file filtered.json --limit 1000
  
  # Show detailed statistics
  python extract_articles.py --verbose
        """,
    )

    # File arguments
    parser.add_argument(
        "--input-file",
        default="articles.sql",
        help="SQL dump file to read from (default: articles.sql)",
    )
    parser.add_argument(
        "--output-file",
        default="articles.json",
        help="JSON file to write to (default: articles.json)",
    )

    # Processing options
    parser.add_argument("--limit", type=int, help="Limit number of articles to extract")
    parser.add_argument(
        "--published-only", action="store_true", help="Extract only published articles"
    )
    parser.add_argument(
        "--with-content-only",
        action="store_true",
        help="Extract only articles with content",
    )

    # Output options
    parser.add_argument(
        "--verbose", action="store_true", help="Show detailed extraction progress"
    )
    parser.add_argument(
        "--quiet", action="store_true", help="Suppress output except errors"
    )
    parser.add_argument(
        "--show-sample",
        action="store_true",
        default=True,
        help="Show sample article after extraction (default: True)",
    )
    parser.add_argument(
        "--indent", type=int, default=2, help="JSON indentation level (default: 2)"
    )

    args = parser.parse_args()

    # Validate input file exists
    try:
        with open(args.input_file, "r") as f:
            pass
    except FileNotFoundError:
        print(f"Error: Input file '{args.input_file}' not found", file=sys.stderr)
        sys.exit(1)
    except PermissionError:
        print(f"Error: Permission denied reading '{args.input_file}'", file=sys.stderr)
        sys.exit(1)

    if not args.quiet:
        print(f"📂 Extracting articles from: {args.input_file}")
        print(f"📝 Output file: {args.output_file}")
        if args.limit:
            print(f"📊 Limit: {args.limit} articles")
        print("-" * 50)

    try:
        # Extract articles
        articles = extract_articles_from_sql(args.input_file)

        # Apply filters
        if args.published_only:
            articles = [a for a in articles if a.get("published_time")]
            if not args.quiet:
                print(f"📅 Filtered to {len(articles)} published articles")

        if args.with_content_only:
            articles = [a for a in articles if a.get("content")]
            if not args.quiet:
                print(f"📄 Filtered to {len(articles)} articles with content")

        # Apply limit
        if args.limit and len(articles) > args.limit:
            articles = articles[: args.limit]
            if not args.quiet:
                print(f"⚡ Limited to {args.limit} articles")

        if not args.quiet:
            print(f"\n✅ Successfully extracted {len(articles)} articles")

        # Write to JSON file
        with open(args.output_file, "w", encoding="utf-8") as f:
            if args.indent:
                json.dump(
                    articles, f, ensure_ascii=False, indent=args.indent, default=str
                )
            else:
                json.dump(articles, f, ensure_ascii=False, default=str)

        if not args.quiet:
            print(f"💾 Articles saved to: {args.output_file}")

            # Print summary statistics
            articles_with_content = sum(1 for a in articles if a.get("content"))
            articles_with_category = sum(1 for a in articles if a.get("category"))
            published_articles = sum(1 for a in articles if a.get("published_time"))

            print(f"\n📊 Summary Statistics:")
            print(f"  Total articles: {len(articles)}")
            print(
                f"  With content: {articles_with_content} ({articles_with_content * 100 // len(articles) if articles else 0}%)"
            )
            print(
                f"  With category: {articles_with_category} ({articles_with_category * 100 // len(articles) if articles else 0}%)"
            )
            print(
                f"  Published: {published_articles} ({published_articles * 100 // len(articles) if articles else 0}%)"
            )

            # Calculate content size statistics
            if articles_with_content > 0:
                content_lengths = [
                    len(a["content"]) for a in articles if a.get("content")
                ]
                avg_content_length = sum(content_lengths) // len(content_lengths)
                max_content_length = max(content_lengths)
                min_content_length = min(content_lengths)

                print(f"\n📏 Content Statistics:")
                print(f"  Average length: {avg_content_length:,} characters")
                print(f"  Max length: {max_content_length:,} characters")
                print(f"  Min length: {min_content_length:,} characters")

            # Show sample article
            if args.show_sample and articles and articles_with_content > 0:
                # Find an article with content
                sample = next((a for a in articles if a.get("content")), articles[0])

                print(f"\n📖 Sample Article:")
                print(f"  Title: {sample.get('title', 'N/A')}")
                print(f"  Category: {sample.get('category', 'N/A')}")
                print(f"  Published: {sample.get('published_time', 'N/A')}")
                print(f"  Author ID: {sample.get('author_id', 'N/A')}")

                if sample.get("caption"):
                    preview = (
                        sample["caption"][:100] + "..."
                        if len(sample["caption"]) > 100
                        else sample["caption"]
                    )
                    print(f"  Caption: {preview}")

                if sample.get("content"):
                    preview = (
                        sample["content"][:150] + "..."
                        if len(sample["content"]) > 150
                        else sample["content"]
                    )
                    # Clean up newlines for preview
                    preview = " ".join(preview.split())
                    print(f"  Content: {preview}")

    except Exception as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        if args.verbose:
            import traceback

            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
