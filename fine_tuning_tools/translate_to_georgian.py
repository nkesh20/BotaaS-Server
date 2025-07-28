import pandas as pd
import sys
import os
import time
from google.cloud import translate_v2 as translate
from google.auth import default
import logging
from typing import Optional

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('translation.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class GeorgianTranslator:
    def __init__(self, api_key: Optional[str] = None):
        try:
            if api_key:
                self.client = translate.Client(api_key)
            else:
                # Try to use default credentials
                credentials, project = default()
                self.client = translate.Client(credentials=credentials)
            logger.info("Google Translate client initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Google Translate client: {e}")
            raise
    
    def translate_text(self, text: str, max_retries: int = 3) -> Optional[str]:
        for attempt in range(max_retries):
            try:
                if not text or text.strip() == "":
                    return text
                
                result = self.client.translate(
                    text,
                    target_language='ka',  # Georgian language code
                    source_language='en'   # English language code
                )
                
                translated_text = result['translatedText']
                logger.debug(f"Translated: '{text[:50]}...' -> '{translated_text[:50]}...'")
                return translated_text
                
            except Exception as e:
                logger.warning(f"Translation attempt {attempt + 1} failed: {e}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)  # Exponential backoff
                else:
                    logger.error(f"Failed to translate text after {max_retries} attempts: {text[:100]}")
                    return None
    
    def translate_dataset(self, input_file: str, output_file: str) -> bool:
        try:
            # Read the input CSV file
            logger.info(f"Reading input file: {input_file}")
            df = pd.read_csv(input_file)
            
            # Validate CSV structure
            if len(df.columns) != 2:
                logger.error(f"Expected 2 columns, found {len(df.columns)}")
                return False
            
            # Rename columns for clarity
            df.columns = ['text', 'label']
            
            logger.info(f"Found {len(df)} rows to translate")
            
            # Create a backup of the original data
            backup_file = output_file.replace('.csv', '_backup.csv')
            df.to_csv(backup_file, index=False)
            logger.info(f"Created backup at: {backup_file}")
            
            # Initialize progress tracking
            translated_count = 0
            failed_count = 0
            failed_indices = []
            
            # Translate each row
            for index, row in df.iterrows():
                try:
                    original_text = str(row['text'])
                    label = row['label']
                    
                    # Translate the text
                    translated_text = self.translate_text(original_text)
                    
                    if translated_text is not None:
                        df.at[index, 'text'] = translated_text
                        translated_count += 1
                        
                        # Log progress every 10 translations
                        if translated_count % 10 == 0:
                            logger.info(f"Progress: {translated_count}/{len(df)} translations completed")
                    else:
                        failed_count += 1
                        failed_indices.append(index)
                        logger.warning(f"Failed to translate row {index}: {original_text[:100]}")
                
                except Exception as e:
                    failed_count += 1
                    failed_indices.append(index)
                    logger.error(f"Error processing row {index}: {e}")
                
                # Add a small delay to avoid rate limiting
                time.sleep(0.1)
            
            logger.info(f"Saving translated dataset to: {output_file}")
            df.to_csv(output_file, index=False)
            
            logger.info(f"Translation completed!")
            logger.info(f"Successfully translated: {translated_count}/{len(df)} rows")
            logger.info(f"Failed translations: {failed_count} rows")
            
            if failed_indices:
                logger.warning(f"Failed rows indices: {failed_indices}")
                # Save failed rows to a separate file for manual review
                failed_df = df.iloc[failed_indices]
                failed_file = output_file.replace('.csv', '_failed.csv')
                failed_df.to_csv(failed_file, index=False)
                logger.info(f"Failed rows saved to: {failed_file}")
            
            return True
            
        except Exception as e:
            logger.error(f"Error during dataset translation: {e}")
            return False

def main():
    """Main function to handle command line arguments and execute translation."""
    if len(sys.argv) != 3:
        print("Usage: python translate_to_georgian.py input.csv output.csv")
        print("\nArguments:")
        print("  input.csv   - Path to the input CSV file with English text and labels")
        print("  output.csv  - Path to save the translated Georgian dataset")
        print("\nThe input CSV should have 2 columns: text (English) and label")
        sys.exit(1)
    
    input_file = sys.argv[1]
    output_file = sys.argv[2]
    
    # Validate input file
    if not os.path.exists(input_file):
        logger.error(f"Input file not found: {input_file}")
        sys.exit(1)
    
    # Check if output directory exists
    output_dir = os.path.dirname(output_file)
    if output_dir and not os.path.exists(output_dir):
        try:
            os.makedirs(output_dir)
            logger.info(f"Created output directory: {output_dir}")
        except Exception as e:
            logger.error(f"Failed to create output directory: {e}")
            sys.exit(1)
    
    try:
        # Get API key from environment variable
        api_key = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
        if not api_key:
            logger.error("GOOGLE_TRANSLATE_API_KEY environment variable not set")
            sys.exit(1)
        
        # Initialize translator with API key
        translator = GeorgianTranslator(api_key=api_key)
        
        # Perform translation
        success = translator.translate_dataset(input_file, output_file)
        
        if success:
            logger.info("Translation completed successfully!")
        else:
            logger.error("Translation failed!")
            sys.exit(1)
            
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 