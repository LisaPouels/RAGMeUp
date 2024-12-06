from rank_bm25 import BM25Okapi
import sqlite3
import pandas as pd
import os

class Reranker:
    def __init__(self, feedback_db='feedback.db', data_directory='data'):
        self.feedback_db = feedback_db
        self.data_dir = os.getenv(data_directory)


    def get_feedback_reranker(self):
        """
        Fetch feedback for a specific document from the feedback database.
        """
        conn = sqlite3.connect(self.feedback_db)
        
        query = """
        SELECT query, answer, document_id, rating
        FROM Feedback 
        """
        
        feedback = pd.read_sql_query(query, conn)
        conn.close()
        return feedback
    
    def get_documents_reranker(self):
        """
        Retrieve a list of documents from the data directory.

        This endpoint checks the configured data directory and returns a list of files
        that match the specified file types.

        Returns:
            JSON response containing the list of files.
        # """   
  
        os.environ['data_directory'] = 'data'
        os.environ["file_types"] = "txt,csv,pdf,json"

        data_directory = os.getenv('data_directory')
        file_types = os.getenv("file_types", "").split(",")

        # Filter files based on specified types
        files = [f for f in os.listdir(data_directory)
                if os.path.isfile(os.path.join(data_directory, f)) and os.path.splitext(f)[1][1:] in file_types]
        
        print('files in get_documents_reranker:', files)
        
        return files
        
    
    def combiner(self, feedback, documents_lst):
        """ Combine the feedback and documents into a single DataFrame."""
        
        # Iterate through the feedback DataFrame
        for doc in range(len(feedback['document_id'])):
            document_ids = feedback['document_id'][doc].replace('[', '').replace(']', '').replace(' " ', '').split(',')
            rating = feedback['rating'][doc]

            # Iterate through the document_ids
            for doc_id in range(len(document_ids)):
                document_id = document_ids[doc_id]
                document_id = document_id.strip('"')
                
                # Create a new dataframe with document_id and rating
                new_row = pd.DataFrame({'document_id': [document_id], 'rating': [rating]})
                
                # Check if feedback_rating_df exist otherwise create it
                if 'feedback_rating_df' not in locals():
                    feedback_rating_df = new_row
                    
                # Append the new row to the combined dataframe
                if document_id in feedback_rating_df['document_id'].values:
                    feedback_rating_df.loc[feedback_rating_df['document_id'] == document_id, 'rating'] += rating
                else:
                    feedback_rating_df = pd.concat([feedback_rating_df, new_row], ignore_index=True)

        # Create a dataframe from documents_lst
        documents_df = pd.DataFrame(documents_lst, columns=['document_id'])
                    
        # Merge documents_df with feedback_rating_df on 'document_id'
        combined_df = pd.merge(documents_df, feedback_rating_df, on='document_id', how='left')

        # Fill NaN values in the 'rating' column with 0
        combined_df['rating'].fillna(0, inplace=True)
        # Ensure the 'rating' column is of integer type
        combined_df['rating'] = combined_df['rating'].astype(int)

        return combined_df
                
                            

    def retrieve_with_bm25(self, query, documents):
        """
        Retrieve documents based on BM25 scores.
        """
        # Tokenize the documents
        tokenized_docs = [doc.split() for doc in documents]

        # Initialize BM25
        bm25 = BM25Okapi(tokenized_docs)

        # Tokenize the query
        tokenized_query = query.split()

        # Retrieve scores
        scores = bm25.get_scores(tokenized_query)
        print('scores:', scores)

        # Combine documents with their scores
        retrieved_docs = [{"document": doc, "bm25_score": score} for doc, score in zip(documents, scores)]
        # Convert retrieved_docs to a DataFrame
        retrieved_docs_df = pd.DataFrame(retrieved_docs)
        print('retrieved_docs_df:', retrieved_docs_df)
        return retrieved_docs_df

    
    def compute_relevance_score(self, bm25_score_weight, feedback_weight, alpha=0.7, beta=0.3):
        """
        Compute the relevance score based on BM25 weight and user feedback weight.
        
        Args:
            bm25_score_weight (float): The BM25 relevance score for a document.
            feedback_weight (float): The user feedback weight for a document.
            alpha (float): Weight of BM25 in the relevance formula.
            beta (float): Weight of user feedback in the relevance formula.

        Returns:
            float: Combined relevance score.
        """
       
        return alpha * bm25_score_weight + beta * feedback_weight
    
    def rerank_documents_with_feedback(self, query, documents, feedback, combined_df):
        """
        Rerank documents based on BM25 scores and user feedback.

        Args:
            query (str): User query.
            documents (list of str): List of document texts.
            feedback (DataFrame): User feedback DataFrame with ratings and helpfulness.

        Returns:
            list of dict: Reranked documents with relevance scores.
        """
        
        bm25_df = self.retrieve_with_bm25(query, documents)
        # Merge bm25_df with combined_df on 'document' and 'document_id'
        combined_df = pd.merge(bm25_df, combined_df, left_on='document', right_on='document_id', how='left')

        # Compute relevance scores
        relevance_scores = []
        for i in range(len(combined_df)):
            feedback_score = combined_df['rating'][i]
            bm25_score_reranker = combined_df['bm25_score'][i]
            relevance_score = self.compute_relevance_score(bm25_score_reranker, feedback_score)
            relevance_scores.append(relevance_score)
        combined_df['relevance_score'] = relevance_scores

        # Sort documents by relevance score
        sorted_df = combined_df.sort_values(by='relevance_score', ascending=False)
 
        return sorted_df


          
    def main_reranker(self, query):
        feedback_df = self.get_feedback_reranker()
        documents_lst = self.get_documents_reranker()
        combined_df = self.combiner(feedback_df, documents_lst)
        query = query
        rerank_df = self.rerank_documents_with_feedback(query, documents_lst, feedback_df, combined_df)

        print('Feedback dataframe:',feedback_df)
        print('Combined dataframe:', combined_df)
        print('Sorted datafrme:', rerank_df)
        
        

# The code below is used to test the Reranker class    
def main():
    # Example usage
    try:
        reranker = Reranker()
        reranker.main_reranker('What is Word2Vec?'
        )
    
    except Exception as e:
        print(f"Reranking failed: {e}")
    

if __name__ == "__main__":
    main()
    
