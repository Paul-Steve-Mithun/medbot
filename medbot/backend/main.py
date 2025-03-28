from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel
import langgraph
from langgraph.graph import StateGraph, START
from typing import Dict, List, Optional
from fastapi.middleware.cors import CORSMiddleware
from langchain_groq import ChatGroq
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# Initialize LLM
llm = ChatGroq(model="llama-3.3-70b-versatile", groq_api_key=GROQ_API_KEY)


# Initialize FastAPI
app = FastAPI()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Simulating a persistent database (replace with actual DB if needed)
user_data_store = {}

# User Response Model
class UserResponse(BaseModel):
    user_id: str
    response: str

# User Data Model (for tracking conversation state)
class UserData(BaseModel):
    user_id: str
    history: List[Dict[str, str]] = []
    is_existing: bool = False
    symptoms: List[str] = []
    previous_history: str = ""
    medication_history: str = ""
    additional_symptoms: str = ""
    diagnosis: str = ""
    critical: bool = False

# Function to get user state
def get_user_data(user_id: str):
    return user_data_store.get(user_id, UserData(user_id=user_id))

# Function to update user data with validation details
def update_user_data(user_id: str, key: str, value: str, validation_details=None):
    user = get_user_data(user_id)
    
    # Add the new entry with validation details if provided
    entry = {key: value}
    if validation_details:
        entry["validation_details"] = validation_details
    
    user.history.append(entry)
    
    # Also update specific fields based on key
    if key == "symptoms":
        user.symptoms.append(value)
    elif key == "previous_history":
        user.previous_history = value
    elif key == "medication_history":
        user.medication_history = value
    elif key == "additional_symptoms":
        user.additional_symptoms = value
        if value.lower() not in ["no", "none", "not really", "that's all"]:
            user.symptoms.append(value)
    elif key == "diagnosis":
        user.diagnosis = value
    elif key == "critical":
        user.critical = value.lower() == "yes"
    elif key == "current_question":
        # Just store in history, don't update specific fields
        pass
    elif key == "current_step":
        # Just store in history, don't update specific fields
        pass
    
    user_data_store[user_id] = user

# Define state schema - simplified for clarity
class ChatState(BaseModel):
    user_id: str
    response: Optional[str] = None
    is_existing: Optional[bool] = None
    symptoms: Optional[List] = []
    previous_history: Optional[str] = None
    medication_history: Optional[str] = None
    additional_symptoms: Optional[str] = None
    diagnosis: Optional[str] = None
    critical: Optional[bool] = False
    current_question: Optional[str] = None
    current_step: Optional[str] = "start"
    
    class Config:
        arbitrary_types_allowed = True

# Helper function to ensure we're working with dictionaries
def ensure_dict(state):
    if isinstance(state, dict):
        return state
    elif isinstance(state, ChatState):
        return state.dict()
    else:
        raise ValueError(f"Unexpected state type: {type(state)}")

# Ask question function for conversation flow
def ask_question(state, question, key, next_step):
    try:
        state_dict = ensure_dict(state)
        user_id = state_dict["user_id"]
        user_response = state_dict.get("response")
        
        # Store the response if there is one
        if user_response:
            update_user_data(user_id, key, user_response)
        
        # Set the next question and step
        state_dict["current_question"] = question
        state_dict["current_step"] = next_step
        return state_dict
        
    except Exception as e:
        print(f"Error in ask_question: {str(e)}")
        state_dict = ensure_dict(state) if state else {"user_id": "unknown"}
        state_dict["current_question"] = "I apologize, but I encountered an error. Could you please try again?"
        return state_dict

# Modify the start_node function for proper validation from the beginning
def start_node(state):
    state_dict = ensure_dict(state)
    user_id = state_dict["user_id"]
    user_response = state_dict.get("response", "")
    
    # Check if this is a first-time call vs a response to the greeting
    if not user_response:
        # First time - just set up the user and return a greeting
        user_data = get_user_data(user_id)
        is_new_user = user_id not in user_data_store
        state_dict["is_existing"] = not is_new_user
        
        if is_new_user:
            user_data_store[user_id] = user_data
            state_dict["current_question"] = "Hello! I'm your medical assistant. Could you please describe your symptoms in detail?"
        else:
            state_dict["current_question"] = "Welcome back! How are you feeling today? Please describe your current symptoms in detail."
        
        # Set next step to be symptoms collection
        state_dict["current_step"] = "symptoms"
        return state_dict
    
    # Check if the response appears to be describing symptoms
    # This helps differentiate between a proper symptom response and a greeting
    symptoms_keywords = ["fever", "headache", "pain", "cough", "cold", "sick", "hurts", "ache", 
                         "sore", "throat", "stomach", "nausea", "vomit", "dizzy", "tired", "fatigue"]
    
    lower_response = user_response.lower()
    has_symptoms = any(keyword in lower_response for keyword in symptoms_keywords)
    
    if has_symptoms:
        # User has provided symptoms in their initial response, proceed to symptom collection
        update_user_data(user_id, "symptoms", user_response)
        
        # Next question about previous doctor consultation
        state_dict["current_question"] = "Have you consulted a doctor about these symptoms before? If yes, what was their diagnosis?"
        state_dict["current_step"] = "previous_history"
    else:
        # If the response doesn't contain recognizable symptoms, ask again for symptoms
        update_user_data(user_id, "conversation_note", "User didn't provide clear symptoms in initial response")
        state_dict["current_question"] = "To help you better, I need to understand your symptoms. Could you please describe what health issues you're experiencing?"
        state_dict["current_step"] = "symptoms"
    
    return state_dict

# Modify the conversation flow to strictly follow the steps
# Each function should only handle one step and not skip ahead

# Update the symptom collection node - only ask about symptoms
def collect_symptoms_handler(state):
    state_dict = ensure_dict(state)
    user_id = state_dict["user_id"]
    user_response = state_dict.get("response", "")

    # Check if we have a valid response
    if user_response and user_response != "continue":
        # The response has already been validated, so we can extract symptoms
        update_user_data(user_id, "symptoms", user_response)
    
    # Next question about previous doctor consultation
    state_dict["current_question"] = "Have you consulted a doctor about these symptoms before? If yes, what was their diagnosis?"
    state_dict["current_step"] = "previous_history"
    return state_dict

# Update the previous_history_handler to enforce complete answers
def previous_history_handler(state):
    state_dict = ensure_dict(state)
    user_id = state_dict["user_id"]
    user_response = state_dict.get("response", "")
    
    # Always save the response, even if brief
    update_user_data(user_id, "previous_history", user_response)
    
    # Extract any diagnosis information from the response
    has_consulted_doctor = False
    extracted_diagnosis = ""
    
    # Simple parsing logic for common responses
    lower_response = user_response.lower()
    
    # Check if the response is just "yes" without diagnosis
    if lower_response == "yes":
        # We should keep the same step and ask for the diagnosis
        state_dict["current_question"] = "What was the doctor's diagnosis?"
        state_dict["current_step"] = "previous_history"  # Stay in the same step
        return state_dict
    
    # Process more complex responses
    if "yes" in lower_response or "diagnosed" in lower_response or "doctor said" in lower_response:
        has_consulted_doctor = True
        # Try to extract the diagnosis
        if "with" in lower_response and "diagnosed" in lower_response:
            parts = lower_response.split("with")
            if len(parts) > 1:
                extracted_diagnosis = parts[1].strip()
        elif ":" in lower_response:
            parts = lower_response.split(":")
            if len(parts) > 1:
                extracted_diagnosis = parts[1].strip()
        else:
            # Just use the response if it seems like a condition
            common_conditions = ["fever", "flu", "cold", "infection", "virus", "allergy"]
            for condition in common_conditions:
                if condition in lower_response:
                    extracted_diagnosis = condition
                    break
    
    # If the response itself is just a condition name, extract it
    if lower_response in ["viral fever", "flu", "cold", "fever", "infection"]:
        has_consulted_doctor = True
        extracted_diagnosis = lower_response
    
    # Continue with the conversation flow
    if has_consulted_doctor and extracted_diagnosis:
        symptoms_text = ", ".join(get_user_data(user_id).symptoms)
        similar_diagnosis_prompt = f"For a patient with symptoms {symptoms_text} and a previous diagnosis of {extracted_diagnosis}, suggest 2-3 similar or related possible diagnoses. Keep it brief."
        similar_diagnosis = llm.invoke(similar_diagnosis_prompt)
        response = f"Thank you for sharing that information. Based on your previous diagnosis of {extracted_diagnosis}, some similar conditions could include: {similar_diagnosis.content}\n\nHave you taken any medications for this condition? If yes, what medications and did you experience any side effects?"
        state_dict["current_question"] = response
        state_dict["current_step"] = "medication_history"
    elif has_consulted_doctor and not extracted_diagnosis:
        # If they said yes but didn't provide a diagnosis
        state_dict["current_question"] = "What was the doctor's diagnosis?"
        state_dict["current_step"] = "previous_history"  # Stay in the same step
    else:
        # If they haven't consulted a doctor, move to medication history
        state_dict["current_question"] = "Have you taken any medications for this condition? If yes, what medications and did you experience any side effects?"
        state_dict["current_step"] = "medication_history"
    
    return state_dict

# Update the medication_history_handler with validation awareness
def medication_history_handler(state):
    state_dict = ensure_dict(state)
    user_id = state_dict["user_id"]
    user_response = state_dict.get("response", "")
    
    # Validated response can be processed directly
    update_user_data(user_id, "medication_history", user_response)
    
    # Extract validation details if available
    user_data = get_user_data(user_id)
    validation_details = next((item.get("validation_details") for item in reversed(user_data.history) 
                              if "validation_details" in item), None)
    
    # Customize response based on medication information
    medications = []
    if validation_details and "medications" in validation_details:
        medications = validation_details.get("medications", [])
    
    if medications:
        medication_list = ", ".join(medications)
        state_dict["current_question"] = f"Thank you for sharing that you've taken {medication_list}. Besides what you've already mentioned, are you experiencing any other symptoms that we should know about?"
    else:
        state_dict["current_question"] = "Besides what you've already mentioned, are you experiencing any other symptoms that we should know about?"
    
    state_dict["current_step"] = "additional_symptoms"
    return state_dict

# Update the additional_symptoms_handler to immediately generate diagnosis
def additional_symptoms_handler(state):
    state_dict = ensure_dict(state)
    user_id = state_dict["user_id"]
    user_response = state_dict.get("response", "")
    
    # Save validated additional symptoms
    update_user_data(user_id, "additional_symptoms", user_response)
    
    # Get validation details
    user_data = get_user_data(user_id)
    validation_details = next((item.get("validation_details") for item in reversed(user_data.history) 
                              if "validation_details" in item), None)
    
    has_additional_symptoms = False
    additional_symptoms = []
    
    if validation_details:
        has_additional_symptoms = validation_details.get("has_additional_symptoms", False)
        additional_symptoms = validation_details.get("additional_symptoms", [])
    
    # First, inform user that diagnosis is being prepared
    intermediate_message = ""
    if has_additional_symptoms and additional_symptoms:
        symptoms_list = ", ".join(additional_symptoms)
        intermediate_message = f"Thank you for sharing these additional symptoms: {symptoms_list}. I'll now analyze all your symptoms and provide a preliminary diagnosis."
    else:
        intermediate_message = "Thank you for this information. I'll now analyze your symptoms and provide a preliminary diagnosis."
    
    # Store this intermediate message, but DON'T return it - we'll generate the diagnosis right away
    update_user_data(user_id, "intermediate_message", intermediate_message)
    
    # Generate diagnosis immediately without requiring another user input
    symptoms_text = ", ".join(user_data.symptoms)
    prev_history = user_data.previous_history
    med_history = user_data.medication_history
    add_symptoms = user_data.additional_symptoms
    
    diagnosis_prompt = f"""Based on the following patient information, provide a detailed diagnosis:
    
    Symptoms: {symptoms_text}
    Previous Medical History: {prev_history}
    Medication History: {med_history}
    Additional Symptoms: {add_symptoms}
    
    Format your diagnosis as a clear bulleted list with:
    • Most likely condition(s)
    • Brief explanation for each condition
    • Key symptoms supporting this diagnosis
    
    Use bullet points (•) for main points and sub-bullets (-) for details.
    """
    
    diagnosis = llm.invoke(diagnosis_prompt)
    update_user_data(user_id, "diagnosis", diagnosis.content)
    
    # Set the diagnosis as the current question and move to criticality step
    state_dict["current_question"] = diagnosis.content
    state_dict["current_step"] = "criticality"
    return state_dict

# Update the diagnosis prep handler for bullet-point format
def diagnosis_prep_handler(state):
    state_dict = ensure_dict(state)
    user_id = state_dict["user_id"]
    
    # This function should directly generate the diagnosis and return it
    user_data = get_user_data(user_id)
    
    # Generate diagnosis
    symptoms_text = ", ".join(user_data.symptoms)
    prev_history = user_data.previous_history
    med_history = user_data.medication_history
    add_symptoms = user_data.additional_symptoms
    
    diagnosis_prompt = f"""Based on the following patient information, provide a detailed diagnosis:
    
    Symptoms: {symptoms_text}
    Previous Medical History: {prev_history}
    Medication History: {med_history}
    Additional Symptoms: {add_symptoms}
    
    Format your diagnosis as a clear bulleted list with:
    - Most likely condition(s)
    - Brief explanation for each condition
    - Key symptoms supporting this diagnosis
    
    Use bullet points (•) for main points and sub-bullets (-) for details.
    """
    
    diagnosis = llm.invoke(diagnosis_prompt)
    update_user_data(user_id, "diagnosis", diagnosis.content)
    
    # Set the diagnosis as the current question and move to criticality step
    state_dict["current_question"] = diagnosis.content
    state_dict["current_step"] = "criticality"
    return state_dict

# Update the generate_diagnosis function for bullet-point format
def generate_diagnosis(state):
    state_dict = ensure_dict(state)
    user_id = state_dict["user_id"]
    user_data = get_user_data(user_id)
    
    # Generate diagnosis
    symptoms_text = ", ".join(user_data.symptoms)
    prev_history = user_data.previous_history
    med_history = user_data.medication_history
    add_symptoms = user_data.additional_symptoms
    
    diagnosis_prompt = f"""Based on the following patient information, provide a detailed diagnosis:
    
    Symptoms: {symptoms_text}
    Previous Medical History: {prev_history}
    Medication History: {med_history}
    Additional Symptoms: {add_symptoms}
    
    Format your diagnosis as a clear bulleted list with:
    • Most likely condition(s)
    • Brief explanation for each condition
    • Key symptoms supporting this diagnosis
    
    Use bullet points (•) for main points and sub-bullets (-) for details.
    """
    
    diagnosis = llm.invoke(diagnosis_prompt)
    update_user_data(user_id, "diagnosis", diagnosis.content)
    
    state_dict["current_question"] = diagnosis.content
    state_dict["current_step"] = "criticality"
    return state_dict

# Criticality assessment
def assess_criticality(state):
    state_dict = ensure_dict(state)
    user_id = state_dict["user_id"]
    user_data = get_user_data(user_id)
    
    # Assess criticality
    symptoms_text = ", ".join(user_data.symptoms)
    prev_history = user_data.previous_history
    med_history = user_data.medication_history
    diagnosis = user_data.diagnosis
    
    criticality_prompt = f"""Based on the following patient information:
    
    Symptoms: {symptoms_text}
    Previous Medical History: {prev_history}
    Medication History: {med_history}
    Diagnosis: {diagnosis}
    
    Assess the urgency/severity of this condition. 
    1. Is immediate medical attention required? Answer only 'yes' or 'no'.
    2. When should the patient see a doctor? (immediately, within 24 hours, within a week, routine appointment)
    3. What precautions should the patient take in the meantime?
    
    Format your response as:
    Urgency: Yes/No
    Timeframe: [timeframe]
    Precautions: [brief list of precautions]
    """
    
    assessment = llm.invoke(criticality_prompt)
    assessment_text = assessment.content
    
    # Extract urgency
    is_critical = "urgency: yes" in assessment_text.lower()
    update_user_data(user_id, "critical", "yes" if is_critical else "no")
    
    # Format final response with recommendations
    final_response = f"""Based on your information, here's my assessment:

{assessment_text}

DISCLAIMER: This is not a substitute for professional medical advice. Always consult with a qualified healthcare provider for proper diagnosis and treatment.
"""
    
    state_dict["current_question"] = final_response
    state_dict["current_step"] = "end"
    return state_dict

# Add a new handler for generating summary
def generate_summary(state):
    state_dict = ensure_dict(state)
    user_id = state_dict["user_id"]
    user_data = get_user_data(user_id)
    
    if not user_data or not user_data.symptoms:
        return {"summary": "## Medical Case Summary\n\nInsufficient data to generate a medical case summary. Please complete the consultation."}
    
    # Create a professional medical summary for doctors
    symptoms_text = ", ".join(user_data.symptoms)
    
    # Extract validation details for more accurate summary
    history_with_validation = [item for item in user_data.history if "validation_details" in item]
    extracted_details = {}
    
    for entry in history_with_validation:
        validation = entry.get("validation_details", {})
        if "extracted_symptoms" in validation:
            extracted_details["symptoms"] = validation["extracted_symptoms"]
        if "extracted_diagnosis" in validation:
            extracted_details["diagnosis"] = validation["extracted_diagnosis"]
        if "medications" in validation:
            extracted_details["medications"] = validation["medications"]
        if "side_effects" in validation:
            extracted_details["side_effects"] = validation["side_effects"]
    
    summary_prompt = f"""Generate a concise, professional medical case summary for a doctor based on the following patient information:
    
    Presenting Symptoms: {symptoms_text}
    Medical History: {user_data.previous_history}
    Medication History: {user_data.medication_history}
    Additional Symptoms: {user_data.additional_symptoms}
    Preliminary Diagnosis: {user_data.diagnosis}
    Urgency Assessment: {"Urgent medical attention recommended" if user_data.critical else "Routine follow-up recommended"}
    
    Additional Extracted Details: {extracted_details}
    
    Format the summary as a professional medical case summary that a physician would find useful. Include only factual information provided by the patient. Structure the summary with clear headings for Chief Complaint, History, Medications, Assessment, and Recommendations.
    """
    
    summary = llm.invoke(summary_prompt)
    return {"summary": f"## Medical Case Summary\n\n{summary.content}"}

# Define the graph with updated nodes and flow
graph = StateGraph(state_schema=ChatState)

# Define nodes with clear separate steps
graph.add_node("start", start_node)
graph.add_node("collect_symptoms", collect_symptoms_handler)
graph.add_node("prev_history_node", previous_history_handler)
graph.add_node("med_history_node", medication_history_handler)
graph.add_node("additional_symptoms_node", additional_symptoms_handler)
graph.add_node("diagnosis_prep", diagnosis_prep_handler)
graph.add_node("diagnosis_node", generate_diagnosis)
graph.add_node("criticality_node", assess_criticality)
graph.add_node("summary_node", generate_summary)

# Connect from the START constant to your first node
graph.add_edge(START, "start")

# Then keep your other edges as they are
graph.add_edge("start", "collect_symptoms")
graph.add_edge("collect_symptoms", "prev_history_node")
graph.add_edge("prev_history_node", "med_history_node")
graph.add_edge("med_history_node", "additional_symptoms_node")
graph.add_edge("additional_symptoms_node", "diagnosis_prep")
graph.add_edge("diagnosis_prep", "diagnosis_node")
graph.add_edge("diagnosis_node", "criticality_node")

# Compile Graph
chatbot = graph.compile()

# Chat endpoint
@app.post("/chat")
async def chat(user_response: UserResponse):
    try:
        print(f"Received request: {user_response}")
        user_id = user_response.user_id
        
        # Special handling for "continue" token to always proceed to next step
        if user_response.response == "continue":
            if user_id in user_data_store:
                user = user_data_store[user_id]
                current_step = next((item.get("current_step") for item in reversed(user.history) 
                                   if "current_step" in item), "start")
                
                # Force progress to next step in the flow
                state_dict = {
                    "user_id": user_id,
                    "response": "continue",
                    "is_existing": True,
                    "symptoms": user.symptoms,
                    "previous_history": user.previous_history,
                    "medication_history": user.medication_history,
                    "additional_symptoms": user.additional_symptoms,
                    "diagnosis": user.diagnosis,
                    "critical": user.critical,
                    "current_step": current_step
                }
                
                # If we're at the additional_symptoms step, we need to move to diagnosis
                if current_step == "additional_symptoms":
                    next_step = determine_next_step(state_dict)
                else:
                    next_step = determine_next_step(state_dict)
                
                # Process the next step
                next_state = process_step(next_step, state_dict)
                
                # Extract question and step
                question = next_state.get("current_question", "What can I help you with?")
                step = next_state.get("current_step", "unknown")
                
                # Store the current question and step
                update_user_data(user_id, "current_question", question)
                update_user_data(user_id, "current_step", step)
                
                return {"next_question": question, "current_step": step}
        
        # Check if this is a first-time interaction with this user
        is_first_interaction = user_id not in user_data_store
        
        # Check if we have a persistent state for this user
        if not is_first_interaction:
            # Get existing user
            user = user_data_store[user_id]
            
            # Extract current step to determine next action
            current_step = next((item.get("current_step") for item in reversed(user.history) 
                               if "current_step" in item), "start")
            
            # Create a state dict based on where we are in the conversation
            state_dict = {
                "user_id": user_id,
                "response": user_response.response,
                "is_existing": True,
                "symptoms": user.symptoms,
                "previous_history": user.previous_history,
                "medication_history": user.medication_history,
                "additional_symptoms": user.additional_symptoms,
                "diagnosis": user.diagnosis,
                "critical": user.critical,
                "current_step": current_step
            }
            
            # Skip validation for special tokens
            skip_validation = user_response.response in ["continue", "continue_anyway"]
            
            if not skip_validation:
                # Get the previous question to validate against
                previous_question = next((item.get("current_question") for item in reversed(user.history) 
                                         if "current_question" in item), "How can I help you?")
                
                # Determine the expected response type based on current step
                expected_type_map = {
                    "start": "symptoms",
                    "symptoms": "symptoms",
                    "previous_history": "previous_history",
                    "medication_history": "medication_history",
                    "additional_symptoms": "additional_symptoms",
                    "diagnosis_prep": "general",
                    "diagnosis": "general",
                    "criticality": "general",
                    "end": "general"
                }
                expected_type = expected_type_map.get(current_step, "general")
                
                # When processing validation results, check for partial answers 
                validation = await validate_response(previous_question, user_response.response, expected_type)
                
                # Store validation details for future use
                validation_details = validation.get("details", {})
                
                # If the response is invalid but it's a partial answer to a multi-part question
                if not validation["is_valid"]:
                    if validation_details.get("partial_answer", False):
                        # Store the partial answer but stay on the same step
                        update_user_data(user_id, "partial_" + current_step, user_response.response, validation_details)
                        
                        return {
                            "next_question": validation["feedback"],
                            "current_step": current_step  # Stay on the same step
                        }
                    else:
                        # Regular invalid response
                        return {
                            "next_question": validation["feedback"],
                            "current_step": current_step  # Stay on the same step
                        }
                
                # Update the response with processed version
                state_dict["response"] = validation["processed_response"]
                
                # Store validation details
                update_user_data(user_id, "validation", "valid", validation_details)
            elif user_response.response == "continue_anyway":
                # For continue_anyway, use the previous user response but skip validation
                last_user_response = next((item.get("response") for item in reversed(user.history) 
                                          if "response" in item), "")
                state_dict["response"] = last_user_response
            
        else:
            # FIXED PART: New user with initial symptoms - bypass the greeting and go straight to processing
            # Create a new user and process their first response as symptoms
            user_data_store[user_id] = UserData(user_id=user_id)
            
            # Check if the first message contains symptoms
            symptoms_keywords = ["fever", "headache", "pain", "cough", "cold", "sick", "hurts", "ache", 
                               "sore", "throat", "stomach", "nausea", "vomit", "dizzy", "tired", "fatigue"]
            
            initial_response_has_symptoms = any(keyword in user_response.response.lower() for keyword in symptoms_keywords)
            
            if initial_response_has_symptoms:
                # If symptoms are found in the first message, process them and move to previous history
                update_user_data(user_id, "symptoms", user_response.response)
                
                # Skip the greeting, go directly to the next step
                return {
                    "next_question": "Have you consulted a doctor about these symptoms before? If yes, what was their diagnosis?",
                    "current_step": "previous_history"
                }
            else:
                # If no symptoms in first message, start fresh with a greeting
                state_dict = {
                    "user_id": user_id,
                    "response": "",  # Empty response to trigger greeting
                    "is_existing": False,
                    "symptoms": [],
                    "previous_history": None,
                    "medication_history": None,
                    "additional_symptoms": None,
                    "diagnosis": None,
                    "critical": False,
                    "current_question": None,
                    "current_step": "start"
                }
        
        print(f"Processing state: {state_dict}")
        
        # Update the current step based on the conversation flow
        next_step = determine_next_step(state_dict)
        
        # Process just the specific node for this step
        next_state = process_step(next_step, state_dict)
        
        # Extract question and step from state
        if not isinstance(next_state, dict):
            raise HTTPException(status_code=500, detail=f"Expected dict, got {type(next_state)}")
            
        question = next_state.get("current_question", "What can I help you with?")
        step = next_state.get("current_step", "unknown")
        
        # Store the current question for future validation
        update_user_data(user_id, "current_question", question)
        
        # Store the current step in history for next time
        update_user_data(user_id, "current_step", step)
        
        print(f"Returning question: {question}, step: {step}")
        
        return {"next_question": question, "current_step": step}
    
    except Exception as e:
        print(f"Error in chat endpoint: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

# Helper function to determine the next step based on the current step
def determine_next_step(state):
    current_step = state.get("current_step", "start")
    
    # Define the conversation flow
    step_flow = {
        "start": "start",
        "symptoms": "collect_symptoms",
        "previous_history": "prev_history_node",
        "medication_history": "med_history_node",
        "additional_symptoms": "additional_symptoms_node",
        "diagnosis_prep": "diagnosis_prep",
        "diagnosis": "diagnosis_node",
        "criticality": "criticality_node",
        "end": "end"
    }
    
    return step_flow.get(current_step, "start")

# Process a specific step in the conversation
def process_step(step_name, state):
    state_dict = ensure_dict(state)
    
    # Special cases for steps that should auto-progress
    if step_name == "diagnosis_prep":
        # Skip the intermediate step and directly generate diagnosis
        return diagnosis_prep_handler(state_dict)
    elif step_name == "additional_symptoms_node":
        # Handle the additional_symptoms node specially to auto-progress to diagnosis
        return additional_symptoms_handler(state_dict)
    
    # Rest of your handlers
    handlers = {
        "start": start_node,
        "collect_symptoms": collect_symptoms_handler,
        "prev_history_node": previous_history_handler,
        "med_history_node": medication_history_handler,
        "additional_symptoms_node": additional_symptoms_handler,
        "diagnosis_prep": diagnosis_prep_handler,
        "diagnosis_node": generate_diagnosis,
        "criticality_node": assess_criticality
    }
    
    handler = handlers.get(step_name)
    
    if handler:
        return handler(state_dict)
    else:
        print(f"Warning: Unknown step requested: {step_name}")
        return start_node(state_dict)

# Helper function to update user state
def update_user_state(user_id, state):
    if user_id not in user_data_store:
        user_data_store[user_id] = UserData(user_id=user_id)
    
    # The state dict is already updated during the specific node handlers
    # This function is mainly to ensure we have a user record
    pass

# Get user data endpoint
@app.get("/user/{user_id}")
def get_user(user_id: str):
    user_data = get_user_data(user_id)
    return user_data

# Debug endpoint
@app.get("/debug/users")
def debug_users():
    return {"user_count": len(user_data_store), "users": {k: v.dict() for k, v in user_data_store.items()}}

# Add this new endpoint for summary generation
@app.post("/generate_summary")
async def generate_summary_endpoint(user_data_request: dict):
    try:
        user_id = user_data_request.get("user_id")
        if not user_id:
            raise HTTPException(status_code=400, detail="User ID is required")
            
        user_data = get_user_data(user_id)
        
        if not user_data or not user_data.symptoms:
            return {"summary": "## Medical Case Summary\n\nInsufficient data to generate a medical case summary. Please complete the consultation."}
        
        # Create a professional medical summary for doctors
        symptoms_text = ", ".join(user_data.symptoms)
        
        # Extract validation details for more accurate summary
        history_with_validation = [item for item in user_data.history if "validation_details" in item]
        extracted_details = {}
        
        for entry in history_with_validation:
            validation = entry.get("validation_details", {})
            if "extracted_symptoms" in validation:
                extracted_details["symptoms"] = validation["extracted_symptoms"]
            if "extracted_diagnosis" in validation:
                extracted_details["diagnosis"] = validation["extracted_diagnosis"]
            if "medications" in validation:
                extracted_details["medications"] = validation["medications"]
            if "side_effects" in validation:
                extracted_details["side_effects"] = validation["side_effects"]
        
        summary_prompt = f"""Generate a concise, professional medical case summary for a doctor based on the following patient information:
        
        Presenting Symptoms: {symptoms_text}
        Medical History: {user_data.previous_history}
        Medication History: {user_data.medication_history}
        Additional Symptoms: {user_data.additional_symptoms}
        Preliminary Diagnosis: {user_data.diagnosis}
        Urgency Assessment: {"Urgent medical attention recommended" if user_data.critical else "Routine follow-up recommended"}
        
        Additional Extracted Details: {extracted_details}
        
        Format the summary as a professional medical case summary that a physician would find useful. Include only factual information provided by the patient. Structure the summary with clear headings for Chief Complaint, History, Medications, Assessment, and Recommendations.
        """
        
        summary = llm.invoke(summary_prompt)
        return {"summary": f"## Medical Case Summary\n\n{summary.content}"}
        
    except Exception as e:
        print(f"Error generating summary: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

# Improved validation function to be more context-aware
async def validate_response(question, response, expected_type):
    """
    Validates if a user response is relevant to the question being asked.
    
    Args:
        question: The question that was asked
        response: The user's response
        expected_type: What kind of answer we expect (symptoms, history, etc.)
    
    Returns:
        dict: Containing validation result, feedback, and processed response
    """
    # Skip validation for continue message (used in auto-continuation)
    if response == "continue":
        return {"is_valid": True, "feedback": None, "processed_response": response}
    
    # Special handling for multi-part questions
    if expected_type == "previous_history" and response.lower() == "yes":
        return {
            "is_valid": False,
            "feedback": "You mentioned seeing a doctor. Could you please also share what diagnosis they provided?",
            "processed_response": response,
            "details": {
                "has_consulted_doctor": True,
                "extracted_diagnosis": "",
                "partial_answer": True
            }
        }
    
    # Less strict validation for short answers
    if len(response.strip()) <= 10:
        # Only challenge very short answers for symptom collection
        if expected_type == "symptoms" and response.lower() in ["hi", "hello"]:
            return {
                "is_valid": False,
                "feedback": "I need to understand your symptoms to help you. Could you please describe what health issues you're experiencing in more detail?",
                "processed_response": response,
                "details": {"is_valid": False, "reason": "Greeting instead of symptoms"}
            }
        # For previous_history, allow short answers like "no" or "viral fever"
        elif expected_type == "previous_history":
            # Common short answers to medical history questions are valid
            has_consulted = "yes" in response.lower()
            extracted_diagnosis = response if "no" not in response.lower() else ""
            
            return {
                "is_valid": True, 
                "feedback": None, 
                "processed_response": response,
                "details": {
                    "is_valid": True,
                    "has_consulted_doctor": has_consulted,
                    "extracted_diagnosis": extracted_diagnosis
                }
            }
        # For other steps, short answers are usually valid
        else:
            return {"is_valid": True, "feedback": None, "processed_response": response}
    
    # Check if this is a multi-part question and if all parts are answered
    multi_part_check = validate_multi_part_response(question, response, expected_type)
    
    if not multi_part_check["is_complete"]:
        return {
            "is_valid": False,
            "feedback": f"Could you please also tell me about {multi_part_check['missing_part']}?",
            "processed_response": response,
            "details": {
                "is_valid": False,
                "reason": f"Incomplete answer to multi-part question. Missing: {multi_part_check['missing_part']}",
                "partial_answer": True
            }
        }
    
    # Set up validation prompts for different expected response types
    validation_prompts = {
        "previous_history": f"""
            As a medical assistant, evaluate if the following response addresses medical history or doctor consultations.
            The question is about whether the patient has consulted a doctor about their symptoms before.
            A simple "yes" or "no" is valid. A diagnosis name like "viral fever" is a valid response.
            
            Question: "{question}"
            User Response: "{response}"
            
            Format your response as JSON:
            {{
                "is_valid": true/false,
                "reason": "brief explanation",
                "has_consulted_doctor": true/false,
                "extracted_diagnosis": "diagnosis" (if applicable)
            }}
            
            NOTE: Be very lenient in your evaluation. If the response could reasonably be interpreted as a 
            previous diagnosis or an indication they have/have not seen a doctor, mark it as valid.
        """,
        "symptoms": f"""
            As a medical assistant, evaluate if the following response describes medical symptoms.
            
            Question: "{question}"
            User Response: "{response}"
            
            First, determine if the user is describing any medical symptoms or health concerns.
            If yes, extract and list those symptoms.
            If no, explain why the response doesn't describe symptoms.
            
            Format your response as JSON:
            {{
                "is_valid": true/false,
                "reason": "brief explanation",
                "extracted_symptoms": ["symptom1", "symptom2"] (if applicable)
            }}
        """,
        "medication_history": f"""
            As a medical assistant, evaluate if the following response addresses medication history.
            
            Question: "{question}"
            User Response: "{response}"
            
            Determine if the user is describing medications they've taken.
            If yes, extract the medications mentioned. If they mention side effects, note those too.
            If no medications are mentioned or the response is off-topic, explain why.
            
            Format your response as JSON:
            {{
                "is_valid": true/false,
                "reason": "brief explanation",
                "medications": ["medication1", "medication2"] (if applicable),
                "side_effects": ["side effect1", "side effect2"] (if applicable)
            }}
        """,
        "additional_symptoms": f"""
            As a medical assistant, evaluate if the following response addresses additional symptoms.
            
            Question: "{question}"
            User Response: "{response}"
            
            Determine if the user is describing additional symptoms beyond what they've mentioned before.
            If yes, extract those additional symptoms.
            If they clearly state they have no additional symptoms, this is also valid.
            If the response is off-topic, explain why.
            
            Format your response as JSON:
            {{
                "is_valid": true/false,
                "reason": "brief explanation",
                "has_additional_symptoms": true/false,
                "additional_symptoms": ["symptom1", "symptom2"] (if applicable)
            }}
        """,
        "general": f"""
            As a medical assistant, evaluate if the following response is relevant to the question.
            
            Question: "{question}"
            User Response: "{response}"
            
            Determine if the user's response is addressing the question in a meaningful way.
            
            Format your response as JSON:
            {{
                "is_valid": true/false,
                "reason": "brief explanation",
                "processed_response": "cleaned up version of response" (if applicable)
            }}
        """
    }
    
    # Use the appropriate validation prompt (default to general if not specified)
    prompt = validation_prompts.get(expected_type, validation_prompts["general"])
    
    try:
        # Use the LLM to validate the response
        validation_result = llm.invoke(prompt)
        
        # Extract JSON from the response
        import json
        import re
        
        # Look for a JSON pattern in the response
        json_pattern = r'\{.*\}'
        json_match = re.search(json_pattern, validation_result.content, re.DOTALL)
        
        if json_match:
            validation_json = json.loads(json_match.group())
        else:
            # If JSON parsing fails, default to valid
            validation_json = {
                "is_valid": True,  # Default to valid to avoid frustrating users
                "reason": "Could not determine validity",
                "processed_response": response
            }
        
        # Prepare feedback message if response is invalid
        feedback = None
        if not validation_json.get("is_valid", True):
            feedback = f"I notice your response doesn't seem to address my question about {expected_type}. {validation_json.get('reason', '')} Could you please provide more specific information?"
        
        return {
            "is_valid": validation_json.get("is_valid", True),
            "feedback": feedback,
            "processed_response": validation_json.get("processed_response", response),
            "details": validation_json
        }
        
    except Exception as e:
        print(f"Validation error: {str(e)}")
        # Fall back to accepting the response to avoid blocking the conversation
        return {"is_valid": True, "feedback": None, "processed_response": response}

# Add a helper function to identify multi-part questions and check completeness
def validate_multi_part_response(question, response, expected_type):
    """
    Checks if a response answers all parts of a multi-part question
    
    Returns:
        dict: with is_complete flag and missing_part information
    """
    # Define patterns for multi-part questions
    multi_part_patterns = {
        "previous_history": {
            "parts": ["Have you consulted a doctor", "what was their diagnosis"],
            "triggers": ["yes", "i have", "i did", "consulted"],
            "required_follow_up": ["diagnosis", "said", "told me", "found"],
        },
        "medication_history": {
            "parts": ["Have you taken any medications", "what medications", "side effects"],
            "triggers": ["yes", "i have", "i did", "taking", "took"],
            "required_follow_up": ["medication", "drug", "pill", "medicine", "paracetamol", "ibuprofen"],
        },
    }
    
    # Check if we have a pattern for this type
    if expected_type not in multi_part_patterns:
        return {"is_complete": True}
    
    pattern = multi_part_patterns[expected_type]
    lower_response = response.lower()
    
    # Check if any triggers are present
    has_trigger = any(trigger in lower_response for trigger in pattern["triggers"])
    
    if has_trigger:
        # Check if any required follow-up is present
        has_follow_up = any(follow_up in lower_response for follow_up in pattern["required_follow_up"])
        
        if not has_follow_up:
            # Determine which part needs to be answered based on the question pattern
            missing_part = pattern["parts"][1] if pattern["parts"][0] in question.lower() else pattern["parts"][0]
            return {
                "is_complete": False,
                "missing_part": missing_part
            }
    
    return {"is_complete": True}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
