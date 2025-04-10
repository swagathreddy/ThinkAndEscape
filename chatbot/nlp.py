# import spacy
# from sklearn.feature_extraction.text import CountVectorizer
# from sklearn.linear_model import LogisticRegression
# from textblob import TextBlob


# class NLPProcessor:
#     def __init__(self):
#         self.nlp = spacy.load("en_core_web_sm")
#         self.vectorizer = CountVectorizer()
#         self.classifier = LogisticRegression()

#         # Training data for intent classification
#         training_data = [
#             "check that book", "what's in the book", "solve the puzzle",
#             "give me a hint", "where is the door"
#         ]
#         labels = ["check_room", "check_room", "solve_puzzle", "ask_hint", "check_room"]

#         # Train the intent classifier
#         self.train_intent_classifier(training_data, labels)

#     def train_intent_classifier(self, training_data, labels):
#         # Train a simple intent classifier
#         vectors = self.vectorizer.fit_transform(training_data)
#         self.classifier.fit(vectors, labels)

#     def preprocess_input(self, text):
#         """
#         Preprocess the input text:
#         - Normalize (lowercase, strip spaces).
#         - Map synonyms to standard terms.
#         """
#         synonym_map = {
#             "key board": "keyboard",
#             "piano keys": "piano",
#             "is that keyboard": "keyboard",
#         }
#         text = text.lower().strip()
#         for phrase, standard in synonym_map.items():
#             if phrase in text:
#                 return standard
#         return text


#     def classify_intent(self, text):
#         text = self.preprocess_input(text)
#         try:
#             vector = self.vectorizer.transform([text])
#             intent = self.classifier.predict(vector)[0]
#             return intent
#         except Exception:
#             return "unknown_intent"

#     def extract_entities(self, text):
#         doc = self.nlp(text)
#         return {ent.label_: ent.text for ent in doc.ents}
