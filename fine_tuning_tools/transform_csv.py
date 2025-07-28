import pandas as pd
import numpy as np
import sys

def calculate_toxicity_score(row, weights=None):
    if weights is None:
        weights = {
            'toxic': 0.2,
            'severe_toxic': 0.3,
            'obscene': 0.2,
            'threat': 0.5,
            'insult': 0.3,
            'identity_hate': 0.5
        }
    
    score = 0.0
    total_weight = weights['toxic'] + weights['severe_toxic'] + weights['obscene'] + weights['threat'] + weights['insult'] + weights['identity_hate']    
    score = row['toxic'] * weights['toxic'] + row['severe_toxic'] * weights['severe_toxic'] + row['obscene'] * weights['obscene'] + row['threat'] * weights['threat'] + row['insult'] * weights['insult'] + row['identity_hate'] * weights['identity_hate']
    return score / total_weight

def transform_csv(input_file, output_file, weights=None, max_rows=5000):
   
    try:
        # Read the input CSV file
        print(f"Reading input file: {input_file}")
        df = pd.read_csv(input_file)
        
        print(f"Input file shape: {df.shape}")
        print(f"Input columns: {list(df.columns)}")
        
        # Check if required columns exist
        required_columns = ['comment_text', 'toxic', 'severe_toxic', 'obscene', 'threat', 'insult', 'identity_hate']
        missing_columns = [col for col in required_columns if col not in df.columns]
        
        if missing_columns:
            print(f"Warning: Missing columns: {missing_columns}")
            return
        
        # Calculate scores for all rows first
        print("Calculating toxicity scores for all rows...")
        scores = []
        for index, row in df.iterrows():
            score = calculate_toxicity_score(row, weights)
            scores.append({
                'label': row['comment_text'],
                'score': score
            })
        
        # Create dataframe with scores
        score_df = pd.DataFrame(scores)
        
        # Create score bins for stratification
        print("Creating stratified samples based on score distribution...")
        
        # Define score ranges for stratification
        score_ranges = [
            (0.0, 0.2),    # Very low toxicity
            (0.2, 0.4),    # Low toxicity
            (0.4, 0.6),    # Medium toxicity
            (0.6, 0.8),    # High toxicity
            (0.8, 1.0)     # Very high toxicity
        ]
        
        # Sample evenly from each range
        samples_per_range = max_rows // len(score_ranges)
        remaining_samples = max_rows % len(score_ranges)
        
        stratified_data = []
        
        for i, (min_score, max_score) in enumerate(score_ranges):
            # Filter rows in this score range
            mask = (score_df['score'] >= min_score) & (score_df['score'] < max_score)
            range_data = score_df[mask]
            
            if len(range_data) > 0:
                # Determine how many samples to take from this range
                samples_to_take = samples_per_range
                if i < remaining_samples:  # Distribute remaining samples to first few ranges
                    samples_to_take += 1
                
                # Take samples from this range
                if len(range_data) <= samples_to_take:
                    # Take all available samples from this range
                    sampled_data = range_data
                else:
                    # Randomly sample from this range
                    sampled_data = range_data.sample(n=samples_to_take, random_state=42)
                
                stratified_data.append(sampled_data)
                print(f"Score range {min_score:.1f}-{max_score:.1f}: {len(sampled_data)} samples")
            else:
                print(f"Score range {min_score:.1f}-{max_score:.1f}: No samples available")
        
        # Combine all stratified data
        if stratified_data:
            final_df = pd.concat(stratified_data, ignore_index=True)
            
            # Shuffle the final dataset to avoid clustering by score ranges
            final_df = final_df.sample(frac=1, random_state=42).reset_index(drop=True)
            
            # Ensure we don't exceed max_rows
            if len(final_df) > max_rows:
                final_df = final_df.head(max_rows)
            
            # Save to output file
            final_df.to_csv(output_file, index=False)
            
            print(f"Transformation completed!")
        else:
            print("No data available for transformation")

    except FileNotFoundError:
        print(f"Error: Input file '{input_file}' not found.")
    except Exception as e:
        print(f"Error during transformation: {str(e)}")

def main():
    if len(sys.argv) != 3:
        print(f"Usage: python {sys.argv[0]} <input_file> <output_file>")
        sys.exit(1)
    input_file = sys.argv[1]
    output_file = sys.argv[2]
    
    custom_weights = {
        'toxic': 0.5,           
        'severe_toxic': 0.7,    
        'obscene': 0.4,         
        'threat': 0.8,          
        'insult': 0.7,          
        'identity_hate': 0.6    
    }
    
    transform_csv(input_file, output_file, custom_weights, max_rows=5000)

if __name__ == "__main__":
    main()
