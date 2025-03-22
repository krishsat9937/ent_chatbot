from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from openai import AsyncOpenAI
import os
import asyncio
from dotenv import load_dotenv
import logging
from pydantic import BaseModel
from typing import List, Dict, Any
import json
from utils.preprocess import preprocess_text
from utils.predict import predict_diseases
from utils.drug import search_drug_info
import numpy as np

load_dotenv()

logging.basicConfig(level=logging.DEBUG)  # Debug logging enabled

# Load OpenAI API Key
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise ValueError("Missing OpenAI API key in environment variables.")

# Initialize OpenAI Client (Async)
client = AsyncOpenAI(api_key=OPENAI_API_KEY)

# FastAPI Router
chat_router = APIRouter()

class Message(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    messages: List[Message]

SYSTEM_PROMPT = {
    "role": "system",
    "content": """
        "You are an ENT (Ear, Nose, and Throat) medical assistant. "
        "Your task is to analyze patient messages and extract the **top 3 most relevant ENT-related symptoms** "
        "(e.g., sore throat, ear pain, nasal congestion, dizziness, hearing loss). "
        "If a user mentions symptoms that are **not ENT-related**, politely respond with: "
        "'I'm sorry, but I can only assist with concerns related to the ear, nose, and throat.'"
    """
}

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "extract_top_symptoms",
            "description": "Extracts the top 3 ENT-related symptoms from the user's input.",
            "parameters": {
                "type": "object",
                "properties": {
                    "symptoms": {
                        "type": "string",
                        "description": "Top 3 ENT-related symptoms extracted from user input, comma-separated."
                    }
                },
                "required": ["symptoms"]
            }
        }
    }
]

import json

async def openai_stream_response(messages, medical_advice_data):
    """
    Async generator that streams responses from OpenAI and processes function tool calls.
    """
    try:
        response = await client.chat.completions.create(
            model="gpt-4-turbo",
            messages=[SYSTEM_PROMPT, *messages],
            stream=True,
            tools=TOOLS,
            tool_choice="auto"
        )

        final_tool_calls = {}

        async for chunk in response:
            logging.debug(f"Received chunk: {chunk}")

            # ✅ Safely extract choices and tool_calls
            choices = chunk.choices
            if not choices:
                continue  # ✅ Skip empty chunks

            delta = choices[0].delta
            tool_calls = getattr(delta, "tool_calls", None)

            if tool_calls:
                for tool_call in tool_calls:
                    index = tool_call.index
                    if index not in final_tool_calls:
                        final_tool_calls[index] = {"name": tool_call.function.name, "arguments": ""}
                    
                    # ✅ Accumulate arguments as they come in chunks
                    if tool_call.function and tool_call.function.arguments:
                        final_tool_calls[index]["arguments"] += tool_call.function.arguments

            content = getattr(delta, "content", None)

            # ✅ Maintain the expected response format
            response_data = {
                "id": chunk.id,
                "object": chunk.object,
                "created": chunk.created,
                "model": chunk.model,
                "system_fingerprint": chunk.system_fingerprint,
                "choices": [
                    {
                        "index": choices[0].index,
                        "delta": {
                            "content": content if content else None
                        },
                        "finish_reason": choices[0].finish_reason
                    }
                ]
            }

            yield f"data: {json.dumps(response_data)}\n\n"


        # ✅ Process function calls after fully receiving arguments
        for index, tool_call in final_tool_calls.items():
            if tool_call["name"] == "extract_top_symptoms":
                try:
                    extracted_args = json.loads(tool_call["arguments"])  # ✅ Ensure proper JSON parsing
                    extracted_symptoms = extracted_args.get("symptoms", "")

                    cleaned_symptoms = preprocess_text(extracted_symptoms)
                    predicted_disease = predict_diseases(cleaned_symptoms)

                    logging.debug(f"Predicted Disease: {predicted_disease} type: {type(predicted_disease)}")

                    medical_advice = "Consult a doctor for an accurate diagnosis and treatment plan."

                    drug_info = search_drug_info(predicted_disease, medical_advice_data, cleaned_symptoms)

                    # Ensure the disease name is formatted correctly
                    if isinstance(predicted_disease, np.ndarray):  # If it's a NumPy array, extract the first element
                        predicted_disease = predicted_disease[0]

                    if not isinstance(predicted_disease, str):  # Final check to ensure it's a string
                        predicted_disease = str(predicted_disease)

                    predicted_disease = predicted_disease.strip().title()  # Format it correctly

                    # Handle cases where no drugs are found
                    if not drug_info.strip() or "No drug recommendations available" in drug_info:
                        drug_section = "🚫 No specific medications found for this condition."
                    else:
                        drug_section = f"### 💊 Recommended Medications\n{drug_info}\n"

                    # Final formatted response string
                    content_string = (
                        f"### 🏥 Predicted Condition\n"
                        f"**Disease:** {predicted_disease}\n\n"
                        f"{drug_section}\n"
                        f"### ⚕️ Medical Advice\n"
                        f"{medical_advice}\n\n"
                        f"🔔 *Note: Consult a healthcare professional before taking any medication.*"
                    )

                    logging.debug(f"Drug Info: {drug_info}")

                    function_response_data = {
                        "id": f"tool-call-{index}",
                        "object": "function_result",
                        "created": int(asyncio.get_event_loop().time()),
                        "model": "gpt-4-turbo",
                        "system_fingerprint": "function_call",
                        "choices": [
                            {
                                "index": index,
                                "delta": {
                                    "content": content_string
                                },
                                "finish_reason": "stop"
                            }
                        ]
                    }

                    yield f"data: {json.dumps(function_response_data)}\n\n"

                except json.JSONDecodeError as e:
                    logging.error(f"JSON Decode Error: {e}")
                    yield f"data: {{'error': 'Invalid function response format'}}\n\n"

        yield "data: [DONE]\n\n"

    except Exception as e:
        logging.error(f"OpenAI API Error: {e}")
        yield f"data: {{'error': 'Error fetching response from OpenAI'}}\n\n"


@chat_router.post("/chat")
async def chat(request: Request, chat_request: ChatRequest):
    """
    Endpoint for streaming OpenAI chat responses with function tooling.
    """
    
    messages = chat_request.messages
    medical_advice_data = request.app.state.medical_advice_data

    if not messages:
        raise HTTPException(status_code=400, detail="Missing 'messages' field in request body.")

    return StreamingResponse(openai_stream_response(messages, medical_advice_data), media_type="text/event-stream")

def generate_advice(disease: str) -> str:
    """
    Generates medical advice based on predicted disease.
    """
    advice_map = {
        "Common Cold": "Stay hydrated, rest, and take over-the-counter cold medications.",
        "Flu": "Drink plenty of fluids, rest, and consult a doctor if symptoms persist.",
        "Otitis Media": "If ear pain persists, consult an ENT specialist immediately.",
        "Allergic Rhinitis": "Avoid allergens, use antihistamines, and keep indoor air clean."
    }
    return advice_map.get(disease, "Consult a doctor for an accurate diagnosis and treatment plan.")
