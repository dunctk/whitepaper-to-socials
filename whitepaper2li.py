#!/usr/bin/env python3
"""
Whitepaper to LinkedIn Post Converter

This tool converts PDF whitepapers into LinkedIn social media posts by:
1. Converting PDF to Markdown using markitdown
2. Extracting chart/figure images
3. Analyzing images with GPT-4o Vision
4. Generating LinkedIn posts with GPT-4.1
5. Storing posts in NocoDB
"""

import argparse
import hashlib
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import click
import requests
from openai import OpenAI
from PIL import Image
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class WhitepaperProcessor:
    def __init__(self, pdf_path: str, nocodb_table: str, test_mode: bool = False):
        self.pdf_path = Path(pdf_path)
        self.nocodb_table = nocodb_table
        self.test_mode = test_mode
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

        # Initialize state database
        self.db_path = "state.db"
        self._init_db()

        # NocoDB configuration
        self.nocodb_base_url = os.getenv("NOCODB_BASE_URL")
        self.nocodb_api_key = os.getenv("NOCODB_API_KEY")
        self.nocodb_table_id = os.getenv("NOCODB_TABLE_ID")
        self.nocodb_base_id = os.getenv("NOCODB_BASE_ID")
        
        # Whitepaper name
        self.whitepaper_name = os.getenv("WHITEPAPER_NAME", "our latest whitepaper")

    def _init_db(self):
        """Initialize SQLite database for state tracking"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS processing_state (
                pdf_sha256 TEXT,
                image_index INTEGER,
                processed BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (pdf_sha256, image_index)
            )
        """)
        conn.commit()
        conn.close()

    def _get_pdf_hash(self) -> str:
        """Calculate SHA-256 hash of the PDF file"""
        with open(self.pdf_path, 'rb') as f:
            return hashlib.sha256(f.read()).hexdigest()

    def _convert_pdf_to_markdown(self) -> str:
        """Convert PDF to Markdown using markitdown CLI (cached)"""
        slug = self.pdf_path.stem
        output_path = f"/tmp/{slug}.md"

        # Check if markdown file already exists
        if os.path.exists(output_path):
            click.echo(f"Using existing markdown file: {output_path}")
            with open(output_path, 'r', encoding='utf-8') as f:
                return f.read()

        # Convert PDF to markdown
        click.echo(f"Converting PDF to markdown: {output_path}")
        try:
            result = subprocess.run([
                "markitdown", str(self.pdf_path), "-o", output_path
            ], capture_output=True, text=True, check=True)

            with open(output_path, 'r', encoding='utf-8') as f:
                return f.read()
        except subprocess.CalledProcessError as e:
            click.echo(f"Error converting PDF: {e}", err=True)
            sys.exit(1)

    def _extract_images(self, markdown_content: str) -> List[str]:
        """Extract image paths from content_inputs/images/ directory"""
        images_dir = Path("content_inputs/images")
        if not images_dir.exists():
            return []

        # Get all PNG images from the directory
        image_files = list(images_dir.glob("images-*.png"))
        image_files.sort()  # Sort by filename for consistent ordering

        # Filter images >300px wide
        valid_images = []
        for img_path in image_files:
            try:
                with Image.open(img_path) as img:
                    if img.width > 300:
                        valid_images.append(str(img_path))
            except Exception:
                continue

        return valid_images

    def _analyze_image(self, image_path: str) -> Dict:
        """Analyze image using GPT-4o Vision"""
        with open(image_path, 'rb') as image_file:
            import base64
            image_data = base64.b64encode(image_file.read()).decode('utf-8')

        response = self.client.chat.completions.create(
            model="gpt-4.1",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "Analyze this chart/figure and extract key insights. Return a JSON object with 'title', 'key_insights', and 'data_points' fields."
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{image_data}"
                            }
                        }
                    ]
                }
            ],
            max_tokens=1000
        )

        try:
            content = response.choices[0].message.content
            # Handle markdown-wrapped JSON
            if content.strip().startswith('```json'):
                content = content.split('```json')[1].split('```')[0].strip()
            return json.loads(content)
        except (json.JSONDecodeError, IndexError):
            return {"title": "Chart Analysis", "key_insights": response.choices[0].message.content, "data_points": []}

    def _check_content_similarity(self, new_post: str, recent_posts: List[str], threshold: float = 0.7) -> bool:
        """Check if new post is too similar to recent posts using simple word overlap"""
        if not recent_posts:
            return False
            
        new_words = set(new_post.lower().split())
        
        for recent_post in recent_posts:
            recent_words = set(recent_post.lower().split())
            if len(new_words) == 0 or len(recent_words) == 0:
                continue
                
            # Calculate Jaccard similarity (intersection over union)
            intersection = len(new_words.intersection(recent_words))
            union = len(new_words.union(recent_words))
            similarity = intersection / union if union > 0 else 0
            
            if similarity > threshold:
                return True
        return False

    def _get_recent_posts(self, limit: int = 10) -> Tuple[List[str], List[str]]:
        """Get recent post intros and full content for similarity checking"""
        if not all([self.nocodb_base_url, self.nocodb_api_key, self.nocodb_table_id]):
            return [], []

        try:
            headers = {
                'xc-token': self.nocodb_api_key
            }

            url = f"{self.nocodb_base_url}/api/v2/tables/{self.nocodb_table_id}/records?limit={limit}&sort=-CreatedAt"
            response = requests.get(url, headers=headers)
            response.raise_for_status()

            data = response.json()
            recent_intros = []
            recent_full_posts = []

            for record in data.get('list', []):
                post_content = record.get('post', '')
                if post_content:
                    # Extract first 20 words for intro checking
                    words = post_content.split()
                    first_20_words = ' '.join(words[:20])
                    recent_intros.append(first_20_words)
                    recent_full_posts.append(post_content)

            return recent_intros, recent_full_posts

        except Exception as e:
            click.echo(f"Error fetching recent posts: {e}", err=True)
            return [], []

    def _generate_linkedin_posts(self, image_analysis: Dict, whitepaper_content: str = "") -> List[str]:
        """Generate LinkedIn posts using GPT-4.1"""

        # Get recent post intros and full content to avoid repetition
        recent_intros, recent_full_posts = self._get_recent_posts()

        intro_guidance = ""
        if recent_intros:
            intro_guidance = f"""

        CRITICAL: Avoid starting posts with similar language to these recent post beginnings:
        {chr(10).join(f'- "{intro}"' for intro in recent_intros)}

        Use completely different opening approaches that vary in tone and structure.
        """

        # Get current date context
        current_date = datetime.now()
        current_month_year = current_date.strftime("%B %Y")
        
        # Define tone variations with corporate/conversational split (60%/40%)
        corporate_tones = [
            "analytical_professional",
            "data_storytelling", 
            "industry_expert"
        ]
        
        conversational_tones = [
            "conversational_insights",
            "practical_takeaways"
        ]
        
        import random
        
        # Select tones with 60% corporate, 40% conversational weighting
        selected_tones = []
        for _ in range(2):
            if random.random() < 0.6:  # 60% chance for corporate tone
                selected_tones.append(random.choice(corporate_tones))
            else:  # 40% chance for conversational tone
                selected_tones.append(random.choice(conversational_tones))
        
        # Random choice: include report name 30% of the time
        include_report_name = random.random() < 0.3
        report_name_guidance = ""
        
        if include_report_name:
            report_name_guidance = f"""
        
        REPORT REFERENCE: Mention the report name "{self.whitepaper_name}" naturally in the post (not necessarily at the beginning).
        """
        else:
            report_name_guidance = """
        
        REPORT REFERENCE: Do NOT mention the specific report name. Use generic references like "our research", "our latest study", "new data shows", etc.
        """
        
        # Prepare whitepaper context (truncate if too long)
        whitepaper_context = ""
        if whitepaper_content:
            # Truncate whitepaper content to avoid token limits (keep first 8000 chars)
            truncated_content = whitepaper_content[:8000] + "..." if len(whitepaper_content) > 8000 else whitepaper_content
            whitepaper_context = f"""

        FULL WHITEPAPER CONTEXT (for broader understanding):
        {truncated_content}
        """
        
        prompt = f"""
        Based on this specific chart analysis, generate 2 DISTINCTLY DIFFERENT LinkedIn posts with these specific tones:
        Post 1: {selected_tones[0]}
        Post 2: {selected_tones[1]}

        SPECIFIC CHART ANALYSIS (focus your posts on this): {json.dumps(image_analysis, indent=2)}
        {whitepaper_context}
        {report_name_guidance}

        Context: It is currently {current_month_year}. Do not reference future dates.

        TONE GUIDELINES:
        - analytical_professional: Direct, data-focused, corporate but not stuffy
        - conversational_insights: Approachable, question-based, discussion-starter
        - data_storytelling: Narrative approach, "what this means" focus
        - industry_expert: Authoritative but accessible, implications-focused
        - practical_takeaways: Actionable, "here's what you can do" approach

        STRICT REQUIREMENTS:
        - NO emojis whatsoever
        - Break up text with line breaks for readability
        - Maximum 3 hashtags, make them specific and relevant
        - Never use em dashes (—), use other punctuation
        - Write like a real person, not marketing copy
        - Use concrete, specific numbers and facts from the data
        - Each post must take a completely different angle on the same data
        - Keep under 280 words each
        
        VOICE AND PERSPECTIVE:
        - Use first-person plural: "our research", "we found", "our data shows"
        - Speak as the organization that published the research
        - Use only data and insights that are actually present in the chart analysis provided
        
        FORBIDDEN PHRASES (use alternatives):
        Instead of "fascinating insights" → "interesting findings" or "key discoveries" or "notable patterns"  
        Instead of "How does your organization...?" → specific, relevant questions about their actual situation
        Instead of buzzwords like "landscape, paradigm, unlock" → plain business language
        
        DATA ACCURACY:
        - ONLY reference statistics, percentages, and findings that appear in the chart analysis provided
        - Do not invent or assume data points that aren't clearly shown in the analysis
        - If specific numbers aren't clear from the chart, describe trends and patterns instead
        
        OPENING LINE VARIETY (use different approaches):
        - Start with a specific statistic
        - Begin with an observation or trend
        - Open with a surprising finding
        - Lead with a practical insight
        - Start with industry context
        {intro_guidance}

        Return ONLY the post content as plain text, separated by "---POST SEPARATOR---"
        Do NOT use JSON format or markdown formatting.
        """

        response = self.client.chat.completions.create(
            model="gpt-4.1",
            messages=[
                {
                    "role": "system", 
                    "content": "You are a senior business professional writing LinkedIn posts for your organization's research publication. Use 'our research', 'we found', etc. Only reference data that actually appears in the chart analysis provided - never invent statistics. Write authentically, avoiding AI-sounding language and marketing speak."
                },
                {"role": "user", "content": prompt}
            ],
            max_tokens=1500,
            temperature=0.8
        )

        content = response.choices[0].message.content
        # Split by separator and clean up
        posts = content.split("---POST SEPARATOR---")
        
        # Clean up posts, replace em dashes, and check for similarity
        cleaned_posts = []
        for post in posts:
            if post.strip():
                # Replace em dashes with regular dashes as fallback
                cleaned_post = post.strip().replace('—', '-')
                
                # Check if this post is too similar to recent posts
                if self._check_content_similarity(cleaned_post, recent_full_posts, threshold=0.6):
                    click.echo(f"Skipping similar post: {cleaned_post[:50]}...")
                    continue
                    
                cleaned_posts.append(cleaned_post)
        
        # If all posts were filtered out due to similarity, regenerate with stricter guidance
        if not cleaned_posts and recent_full_posts:
            click.echo("All posts were too similar, regenerating with stricter guidance...")
            # Add more specific anti-similarity instruction and try once more
            stricter_prompt = prompt + "\n\nIMPORTANT: The previous attempt was too similar to existing content. Be extremely creative and use completely different approaches, structures, and vocabulary."
            
            response = self.client.chat.completions.create(
                model="gpt-4.1",
                messages=[
                    {
                        "role": "system", 
                        "content": "You are a senior business professional writing LinkedIn posts for your organization's research publication. Use 'our research', 'we found', etc. Only reference data that actually appears in the chart analysis provided - never invent statistics. Focus on being distinctly different from existing content while maintaining authenticity."
                    },
                    {"role": "user", "content": stricter_prompt}
                ],
                max_tokens=1500,
                temperature=0.9
            )
            
            content = response.choices[0].message.content
            posts = content.split("---POST SEPARATOR---")
            
            for post in posts:
                if post.strip():
                    cleaned_post = post.strip().replace('—', '-')
                    cleaned_posts.append(cleaned_post)
        
        return cleaned_posts

    def _upload_image_to_nocodb(self, image_path: str) -> Optional[Dict]:
        """Upload image to NocoDB and return the file info"""
        try:
            # Use the generic file upload endpoint for NocoDB
            url = f"{self.nocodb_base_url}/api/v2/storage/upload"

            headers = {
                'xc-token': self.nocodb_api_key
            }

            with open(image_path, 'rb') as image_file:
                files = {'file': image_file}
                response = requests.post(url, headers=headers, files=files)
                response.raise_for_status()

                upload_result = response.json()
                if upload_result and len(upload_result) > 0:
                    return upload_result[0]

        except Exception as e:
            click.echo(f"Error uploading image to NocoDB: {e}", err=True)
            return None

    def _store_in_nocodb(self, post: str, image_path: str, image_description: str, image_index: int):
        """Store post in NocoDB"""
        if not all([self.nocodb_base_url, self.nocodb_api_key, self.nocodb_table_id, self.nocodb_base_id]):
            click.echo("NocoDB configuration incomplete, saving to CSV instead")
            self._save_to_csv(post, image_path, image_description, image_index)
            return

        # Upload image first
        image_info = self._upload_image_to_nocodb(image_path)
        if not image_info:
            click.echo("Failed to upload image, saving to CSV instead")
            self._save_to_csv(post, image_path, image_description, image_index)
            return

        headers = {
            'Content-Type': 'application/json',
            'xc-token': self.nocodb_api_key
        }

        # Extract key insights as plain text for image description
        if isinstance(image_description, str):
            try:
                # Handle both JSON string and markdown-wrapped JSON
                cleaned_desc = image_description.strip()
                if cleaned_desc.startswith('```json'):
                    # Extract JSON from markdown code block
                    cleaned_desc = cleaned_desc.split('```json')[1].split('```')[0].strip()

                desc_dict = json.loads(cleaned_desc)
                if 'key_insights' in desc_dict:
                    if isinstance(desc_dict['key_insights'], list):
                        plain_description = '\n'.join(desc_dict['key_insights'])
                    else:
                        plain_description = desc_dict['key_insights']
                else:
                    plain_description = image_description
            except (json.JSONDecodeError, IndexError):
                plain_description = image_description
        else:
            plain_description = str(image_description)

        # Extract just the filename from the image path
        image_filename = Path(image_path).name
        
        data = {
            'post': post,
            'image': [image_info],  # NocoDB expects array of objects with full file info
            'image_description': plain_description,
            'image_index': image_index,
            'image_filename': image_filename
        }

        url = f"{self.nocodb_base_url}/api/v2/tables/{self.nocodb_table_id}/records"

        try:
            response = requests.post(url, headers=headers, json=data)
            response.raise_for_status()
            click.echo(f"Stored post for image {image_index} in NocoDB")
        except Exception as e:
            click.echo(f"Error storing in NocoDB: {e}", err=True)
            self._save_to_csv(post, image_path, image_description, image_index)

    def _save_to_csv(self, post: str, image_path: str, image_description: str, image_index: int):
        """Fallback CSV storage"""
        import csv
        date_str = datetime.now().strftime("%Y%m%d")
        csv_path = f"/tmp/posts_{date_str}.csv"

        file_exists = os.path.exists(csv_path)
        with open(csv_path, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            if not file_exists:
                writer.writerow(['post', 'image', 'image_description', 'image_index', 'created_at'])
            writer.writerow([post, image_path, image_description, image_index, datetime.now().isoformat()])

    def _mark_processed(self, pdf_hash: str, image_index: int):
        """Mark image as processed in state database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO processing_state (pdf_sha256, image_index, processed)
            VALUES (?, ?, TRUE)
        """, (pdf_hash, image_index))
        conn.commit()
        conn.close()

    def _get_unprocessed_images(self, pdf_hash: str, total_images: int) -> List[int]:
        """Get list of unprocessed image indices"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT image_index FROM processing_state
            WHERE pdf_sha256 = ? AND processed = TRUE
        """, (pdf_hash,))
        processed = [row[0] for row in cursor.fetchall()]
        conn.close()

        return [i for i in range(total_images) if i not in processed]

    def process(self):
        """Main processing pipeline"""
        click.echo(f"Processing PDF: {self.pdf_path}")

        # Convert PDF to Markdown (cached)
        markdown_content = self._convert_pdf_to_markdown()

        # Extract images from directory
        image_paths = self._extract_images(markdown_content)
        click.echo(f"Found {len(image_paths)} valid images")

        if not image_paths:
            click.echo("No valid images found in PDF")
            return

        # Get PDF hash and unprocessed images
        pdf_hash = self._get_pdf_hash()
        unprocessed_indices = self._get_unprocessed_images(pdf_hash, len(image_paths))

        if not unprocessed_indices:
            click.echo("All images have been processed")
            return

        # Process images
        images_to_process = [unprocessed_indices[0]] if self.test_mode else unprocessed_indices

        for image_index in images_to_process:
            image_path = image_paths[image_index]
            click.echo(f"Processing image {image_index}: {image_path}")

            # Analyze image
            image_analysis = self._analyze_image(image_path)

            # Generate LinkedIn posts
            posts = self._generate_linkedin_posts(image_analysis, markdown_content)

            # Store each post
            for post in posts:
                self._store_in_nocodb(
                    post,
                    image_path,
                    json.dumps(image_analysis),
                    image_index
                )

            # Mark as processed
            self._mark_processed(pdf_hash, image_index)

            if self.test_mode:
                click.echo("Test mode: processed one image")
                break


@click.command()
@click.option('--pdf', required=True, help='Path to PDF whitepaper')
@click.option('--nocodb-table', required=True, help='NocoDB table name')
@click.option('--test', is_flag=True, help='Test mode: process only one image')
def main(pdf, nocodb_table, test):
    """Convert PDF whitepaper to LinkedIn posts"""

    # Check required environment variables
    required_vars = ['OPENAI_API_KEY', 'NOCODB_API_KEY', 'NOCODB_BASE_URL', 'NOCODB_TABLE_ID', 'NOCODB_BASE_ID']
    missing_vars = [var for var in required_vars if not os.getenv(var)]

    if missing_vars:
        click.echo(f"Missing required environment variables: {', '.join(missing_vars)}", err=True)
        sys.exit(1)

    processor = WhitepaperProcessor(pdf, nocodb_table, test)
    processor.process()


if __name__ == '__main__':
    main()
