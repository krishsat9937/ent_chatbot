import joblib
from .preprocess import preprocess_text

model = joblib.load("models/ent_symptom_model.pkl")
vectorizer = joblib.load("models/vectorizer.pkl")
label_encoder = joblib.load("models/label_encoder.pkl")

def predict_diseases(symptom_texts):
    """
    Accepts either a single symptom string or a list of symptom strings.
    Returns the predicted disease(s).
    """
    # If a single string is passed, convert it into a list
    if isinstance(symptom_texts, str):
        symptom_texts = [symptom_texts]

    cleaned_texts = [preprocess_text(text) for text in symptom_texts]    
    
    # Transform the list of symptom strings using the vectorizer
    text_vectorized = vectorizer.transform(cleaned_texts)
    # Get predictions for each text entry
    predictions = model.predict(text_vectorized)
    # Convert numerical labels back to disease names
    predicted_diseases = label_encoder.inverse_transform(predictions)
    return predicted_diseases