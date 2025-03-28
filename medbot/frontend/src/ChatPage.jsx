import { useState, useEffect, useRef } from 'react';
import { FiSend, FiRefreshCw, FiFileText, FiPlus, FiMessageCircle, FiClock, FiCheckCircle, FiAlertCircle } from 'react-icons/fi';
import { MdMedicalServices, MdOutlineHistory, MdOutlineHealthAndSafety } from 'react-icons/md';
import { BsArrowRightCircle, BsExclamationTriangle } from 'react-icons/bs';

const diagnosisStyles = `
  /* Add new styles for the diagnosis card */
  .diagnosis-card {
    background-color: #f0f9ff;
    border: 1px solid #bae6fd;
    border-radius: 0.5rem;
    padding: 1rem;
    margin-bottom: 0.5rem;
  }
  
  .diagnosis-header {
    color: #0369a1;
    font-size: 1rem;
    font-weight: 700;
    margin-top: 0.75rem;
    margin-bottom: 0.5rem;
    border-bottom: 1px solid #bae6fd;
    padding-bottom: 0.25rem;
  }
  
  .diagnosis-content {
    color: #1e3a8a;
    font-weight: 500;
    margin-bottom: 0.75rem;
  }
  
  .diagnosis-list {
    list-style-type: disc;
    padding-left: 1.5rem;
    margin-bottom: 0.75rem;
  }
  
  .diagnosis-list li {
    color: #0284c7;
    margin-bottom: 0.375rem;
    font-weight: 500;
  }
  
  .diagnosis-note {
    font-size: 0.9rem;
    color: #475569;
    font-style: italic;
  }
  
  /* Updated urgent message styling */
  .urgent-message {
    background-color: #fef2f2;
    border: 1px solid #f87171;
    border-radius: 0.5rem;
    padding: 0.75rem;
    margin-bottom: 0.5rem;
  }
  
  .urgent-header {
    color: #dc2626;
    font-size: 1.1rem;
    font-weight: bold;
    margin-bottom: 0.75rem;
    text-align: center;
  }
  
  .urgent-content {
    color: #b91c1c;
    margin-bottom: 0.75rem;
  }
  
  .urgent-content p {
    margin-bottom: 0.5rem;
    display: block;
  }
  
  .urgent-content p strong {
    display: inline-block;
    min-width: 1.5rem;
  }
  
  .urgent-footer {
    font-size: 0.9rem;
    font-weight: bold;
    color: #dc2626;
    margin-top: 0.5rem;
    text-align: center;
  }
`;

const ChatPage = () => {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [chatHistory, setChatHistory] = useState([]);
  const [userId] = useState(`user-${Math.random().toString(36).substr(2, 9)}`);
  const [currentStep, setCurrentStep] = useState('start');
  const [patientData, setPatientData] = useState({
    symptoms: [],
    previous_history: "",
    medication_history: "",
    additional_symptoms: "",
    diagnosis: "",
    critical: false
  });
  const [conversationComplete, setConversationComplete] = useState(false);
  const [showSummaryButton, setShowSummaryButton] = useState(false);
  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  useEffect(() => {
    // Add initial welcome message only once when component mounts
    setMessages([{
      role: 'assistant',
      content: 'Hello! I am your medical assistant. How can I help you today?'
    }]);
    
    // Don't immediately send a backend request here - wait for user input
  }, []);

  useEffect(() => {
    const testBackendConnection = async () => {
      try {
        // Make a simple request to test connectivity
        const testResponse = await fetch('http://localhost:8000/chat', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            user_id: `test-${Date.now()}`,
            response: 'test message'
          }),
        });
        
        const testData = await testResponse.json();
        console.log('Backend connection test:', testData);
        
        if (testResponse.ok) {
          console.log('Backend connection successful');
        } else {
          console.error('Backend connection failed:', testData);
        }
      } catch (error) {
        console.error('Backend connection error:', error);
      }
    };
    
    // testBackendConnection();
  }, []);

  useEffect(() => {
    // If we're at the end of the regular conversation flow, show the summary button
    if (currentStep === "end") {
      setShowSummaryButton(true);
    }
  }, [currentStep]);

  useEffect(() => {
    // Check if the latest message contains any of the auto-continue phrases
    const lastMessage = messages[messages.length - 1];
    if (lastMessage && lastMessage.role === 'assistant') {
      const autoTriggerPhrases = [
        "I'll now analyze your symptoms",
        "analyze all your symptoms and provide a preliminary diagnosis",
        "Thank you for sharing these additional symptoms"
      ];
      
      // Check if any of the trigger phrases are in the message
      const shouldAutoContinue = autoTriggerPhrases.some(phrase => 
        lastMessage.content.includes(phrase)
      );
      
      if (shouldAutoContinue) {
        // Automatically send a continuation request after a short delay
        setTimeout(() => {
          handleContinuation();
        }, 1500); // 1.5 second delay for natural feel
      }
    }
  }, [messages]);

  useEffect(() => {
    const style = document.createElement('style');
    style.innerHTML = diagnosisStyles;
    document.head.appendChild(style);
    return () => {
      document.head.removeChild(style);
    };
  }, []);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!input.trim()) return;

    const userMessage = { role: 'user', content: input };
    
    // Add the user message to the chat (only once)
    setMessages(prev => [...prev, userMessage]);
    
    // Save original input before clearing
    const currentInput = input;
    setInput('');

    try {
      console.log('Sending request with:', {
        user_id: userId,
        response: currentInput
      });

      // Add loading message
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: '...',
        isLoading: true
      }]);

      const response = await fetch('http://localhost:8000/chat', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          user_id: userId,
          response: currentInput
        }),
      });

      // Remove loading message
      setMessages(prev => prev.filter(msg => !msg.isLoading));

      if (!response.ok) {
        const errorData = await response.json();
        console.error('Server error:', errorData);
        throw new Error(errorData.detail || `Server error: ${response.status}`);
      }

      const data = await response.json();
      console.log('Received response:', data);

      if (!data.next_question) {
        throw new Error('Invalid response format from server');
      }

      // FIXED PART: Remove the conditional that was adding the system message and duplicating user message
      // Simply add the bot's response directly
      const botMessage = { role: 'assistant', content: data.next_question };
      setMessages(prev => [...prev, botMessage]);
      
      // Update current step
      if (data.current_step) {
        setCurrentStep(data.current_step);
        
        // Check if conversation is complete
        if (data.current_step === "end") {
          setConversationComplete(true);
          // Fetch user data to update the sidebar
          fetchUserData();
        }
      }
      
      // Update chat history
      updateChatHistory(currentInput, data.next_question);
      
    } catch (error) {
      console.error('Error details:', error);
      // Remove loading message if it exists
      setMessages(prev => prev.filter(msg => !msg.isLoading));
      
      // Add error message
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: `Sorry, I encountered an error: ${error.message}. Please try again.`
      }]);
    }
  };
  
  const updateChatHistory = (userMessage, botResponse) => {
    // Create a new history entry with title based on first few words of user message
    const title = userMessage.length > 20 
      ? userMessage.substring(0, 20) + '...' 
      : userMessage;
      
    const newEntry = {
      id: Date.now(),
      title: title,
      messages: [
        { role: 'user', content: userMessage },
        { role: 'assistant', content: botResponse }
      ]
    };
    
    setChatHistory(prev => [newEntry, ...prev]);
  };
  
  const fetchUserData = async () => {
    try {
      const response = await fetch(`http://localhost:8000/user/${userId}`);
      if (response.ok) {
        const data = await response.json();
        console.log('User data:', data);
        
        setPatientData({
          symptoms: data.symptoms || [],
          previous_history: data.previous_history || "",
          medication_history: data.medication_history || "",
          additional_symptoms: data.additional_symptoms || "",
          diagnosis: data.diagnosis || "",
          critical: data.critical || false
        });
      }
    } catch (error) {
      console.error('Error fetching user data:', error);
    }
  };
  
  const startNewConsultation = () => {
    setMessages([{
      role: 'assistant',
      content: 'Hello! I am your medical assistant. How can I help you today?'
    }]);
    setPatientData({
      symptoms: [],
      previous_history: "",
      medication_history: "",
      additional_symptoms: "",
      diagnosis: "",
      critical: false
    });
    setCurrentStep('start');
    setConversationComplete(false);
  };

  // Current step indicator with icons
  const getStepInfo = () => {
    const stepInfo = {
      "start": { name: "Welcome", icon: <FiMessageCircle /> },
      "symptoms": { name: "Collecting Symptoms", icon: <MdOutlineHealthAndSafety /> },
      "previous_history": { name: "Medical History", icon: <MdOutlineHistory /> },
      "medication_history": { name: "Medication History", icon: <MdMedicalServices /> },
      "additional_symptoms": { name: "Additional Symptoms", icon: <MdOutlineHealthAndSafety /> },
      "diagnosis": { name: "Diagnosis", icon: <FiCheckCircle /> },
      "criticality": { name: "Recommendations", icon: <FiAlertCircle /> },
      "end": { name: "Consultation Complete", icon: <FiCheckCircle /> }
    };
    
    return stepInfo[currentStep] || { name: "Consultation", icon: <FiMessageCircle /> };
  };

  // Add a function to generate the case summary
  const generateCaseSummary = async () => {
    try {
      // Add loading message
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: 'Generating medical case summary...',
        isLoading: true
      }]);

      // Make a special request to generate the summary
      const response = await fetch('http://localhost:8000/generate_summary', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          user_id: userId
        }),
      });

      // Remove loading message
      setMessages(prev => prev.filter(msg => !msg.isLoading));

      if (!response.ok) {
        throw new Error(`Server error: ${response.status}`);
      }

      const data = await response.json();
      
      // Add the summary to the chat
      const summaryMessage = { role: 'assistant', content: data.summary };
      setMessages(prev => [...prev, summaryMessage]);
      
      // Update conversation state
      setConversationComplete(true);
      setShowSummaryButton(false);
      
    } catch (error) {
      console.error('Error generating summary:', error);
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: `Sorry, I encountered an error generating the summary: ${error.message}`
      }]);
    }
  };

  // Add a new function to handle automatic continuation
  const handleContinuation = async () => {
    try {
      console.log('Automatically continuing conversation...');
      
      // Add loading message
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: '...',
        isLoading: true
      }]);

      // Send a continuation request
      const response = await fetch('http://localhost:8000/chat', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          user_id: userId,
          response: "continue" // Send a special token to indicate automatic continuation
        }),
      });

      // Remove loading message
      setMessages(prev => prev.filter(msg => !msg.isLoading));

      if (!response.ok) {
        throw new Error(`Server error: ${response.status}`);
      }

      const data = await response.json();
      
      if (!data.next_question) {
        throw new Error('Invalid response format from server');
      }

      // Add the bot's response to the chat
      const botMessage = { role: 'assistant', content: data.next_question };
      setMessages(prev => [...prev, botMessage]);
      
      // Update current step
      if (data.current_step) {
        setCurrentStep(data.current_step);
        
        if (data.current_step === "end") {
          setConversationComplete(true);
          fetchUserData();
        }
      }
      
    } catch (error) {
      console.error('Error in automatic continuation:', error);
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: `Sorry, I encountered an error: ${error.message}. Please try again.`
      }]);
    }
  };

  // Add logic to determine when a message is invalid feedback
  const isInvalidFeedback = (message) => {
    return message.role === 'assistant' && 
           message.content.includes("doesn't seem to address my question");
  };

  // Add this function to the ChatPage component
  const handleInvalidResponse = async () => {
    try {
      // Add loading message
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: '...',
        isLoading: true
      }]);

      // Send a force continue request
      const response = await fetch('http://localhost:8000/chat', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          user_id: userId,
          response: "continue_anyway" // Special token to bypass validation
        }),
      });

      // Remove loading message
      setMessages(prev => prev.filter(msg => !msg.isLoading));

      if (!response.ok) {
        throw new Error(`Server error: ${response.status}`);
      }

      const data = await response.json();
      
      // Add the bot's response to the chat
      const botMessage = { role: 'assistant', content: data.next_question };
      setMessages(prev => [...prev, botMessage]);
      
      // Update current step
      if (data.current_step) {
        setCurrentStep(data.current_step);
      }
      
    } catch (error) {
      console.error('Error in handling invalid response:', error);
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: `Sorry, I encountered an error: ${error.message}. Please try again.`
      }]);
    }
  };

  // Add this function to manually trigger continuation
  const triggerContinuation = () => {
    handleContinuation();
  };

  // Add this function to the ChatPage component
  const requestDiagnosis = async () => {
    try {
      // Add loading message
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: 'Generating medical diagnosis based on our conversation...',
        isLoading: true
      }]);

      // Request diagnosis
      const response = await fetch('http://localhost:8000/force_diagnosis', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          user_id: userId
        }),
      });

      // Remove loading message
      setMessages(prev => prev.filter(msg => !msg.isLoading));

      if (!response.ok) {
        throw new Error(`Server error: ${response.status}`);
      }

      const data = await response.json();
      
      // Add the diagnosis to the chat
      const diagnosisMessage = { role: 'assistant', content: data.next_question };
      setMessages(prev => [...prev, diagnosisMessage]);
      
      // Update current step
      setCurrentStep(data.current_step);
      
      // If we're now at criticality, fetch user data
      if (data.current_step === "criticality") {
        setConversationComplete(true);
        fetchUserData();
      }
      
    } catch (error) {
      console.error('Error getting diagnosis:', error);
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: `Sorry, I encountered an error generating your diagnosis: ${error.message}`
      }]);
    }
  };

  // Render the message bubbles with updated styling
  const renderMessage = (message, index) => {
    const isInvalid = message.role === 'assistant' && 
                      message.content.includes("doesn't seem to address my question");
                      
    const isPartialAnswer = message.role === 'assistant' && 
                            (message.content.includes("Could you please also tell me about") ||
                             message.content.includes("You mentioned seeing a doctor") ||
                             message.content.includes("also share what diagnosis"));
                    
    const needsContinuation = message.role === 'assistant' && 
                             (message.content.includes("I'll now analyze your symptoms") ||
                              message.content.includes("provide a preliminary diagnosis"));
                      
    // Add a "Get Diagnosis" button after a few exchanges
    const showDiagnosisButton = messages.length > 4 && 
                               message.role === 'assistant' && 
                               !conversationComplete &&
                               !message.content.includes("diagnosis");
                      
    // Check if the message contains HTML
    const containsHTML = message.role === 'assistant' && 
                         (message.content.includes('<div class="') || 
                          message.content.includes('<div class=') ||
                          message.content.includes('</div>'));
                      
    // Detect if this is a likely condition message (diagnosis)
    const isDiagnosis = message.role === 'assistant' && 
                       (message.content.includes('LIKELY CONDITION') || 
                        message.content.includes('## LIKELY CONDITION'));
                      
    // Apply special styling for diagnosis even if not HTML
    const diagnosisStyle = isDiagnosis && !containsHTML ? 'bg-blue-50 border-blue-200' : '';
                      
    return (
      <div
        key={index}
        className={`mb-4 ${
          message.role === 'user' ? 'flex justify-end' : 'flex justify-start'
        }`}
      >
        <div
          className={`p-4 rounded-lg max-w-[80%] shadow-md ${
            message.role === 'user'
              ? 'bg-blue-500 text-white'
              : isInvalid
                ? 'bg-amber-100 text-amber-800 border border-amber-300' 
                : isPartialAnswer
                  ? 'bg-orange-100 text-orange-800 border border-orange-300'
                  : diagnosisStyle || 'bg-white text-gray-800 border border-gray-200'
          } ${message.role === 'assistant' ? 'diagnosis-formatting' : ''}`}
        >
          {/* Render HTML content if it contains HTML */}
          {containsHTML ? (
            <div dangerouslySetInnerHTML={{ __html: message.content }} />
          ) : isDiagnosis ? (
            // Special formatting for diagnosis text that isn't HTML
            <div className="diagnosis-manual">
              {message.content.split('##').map((section, i) => {
                if (i === 0) return null; // Skip anything before the first ##
                
                const [heading, ...contentArr] = section.split('\n');
                const content = contentArr.join('\n').trim();
                
                return (
                  <div key={i} className="mb-3">
                    <div className="text-blue-700 font-bold mb-1">{heading.trim()}</div>
                    <div className="ml-2">{content}</div>
                  </div>
                );
              })}
            </div>
          ) : (
            message.content
          )}
          
          {(isInvalid || isPartialAnswer) && (
            <button
              onClick={handleInvalidResponse}
              className="mt-2 p-1.5 bg-white hover:bg-gray-100 text-gray-800 text-sm rounded-md border border-gray-300 shadow-sm flex items-center gap-1 transition-colors"
            >
              <BsArrowRightCircle size={14} />
              <span>Continue Anyway</span>
            </button>
          )}
          {needsContinuation && (
            <button
              onClick={triggerContinuation}
              className="mt-2 p-1.5 bg-blue-600 hover:bg-blue-700 text-white text-sm rounded-md shadow-sm flex items-center gap-1 transition-colors"
            >
              <BsArrowRightCircle size={14} />
              <span>Get Diagnosis</span>
            </button>
          )}
          {showDiagnosisButton && (
            <button
              onClick={requestDiagnosis}
              className="mt-2 p-1.5 bg-green-600 hover:bg-green-700 text-white text-sm rounded-md shadow-sm flex items-center gap-1 transition-colors"
            >
              <FiFileText size={14} />
              <span>Get Diagnosis</span>
            </button>
          )}
        </div>
      </div>
    );
  };

  const stepInfo = getStepInfo();

  return (
    <div className="flex h-screen bg-gray-50">
      {/* Sidebar - now with light theme */}
      <div className="w-64 bg-white p-4 border-r border-gray-200 shadow-sm">
        <h2 className="text-xl font-bold text-gray-800 mb-4 flex items-center gap-2">
          <MdMedicalServices className="text-blue-500" />
          <span>Medical Assistant</span>
        </h2>
        
        {/* Current step indicator */}
        {currentStep !== 'start' && (
          <div className="mb-4 p-3 bg-blue-50 rounded-lg border border-blue-100">
            <p className="text-gray-500 text-sm mb-1">Current step:</p>
            <div className="flex items-center gap-2 text-blue-700 font-medium">
              {stepInfo.icon}
              <span>{stepInfo.name}</span>
            </div>
          </div>
        )}
        
        {/* Progress steps */}
        <div className="mb-4 p-3 bg-gray-50 rounded-lg border border-gray-200">
          <p className="text-gray-600 text-sm mb-2 font-medium">Consultation Progress</p>
          <div className="space-y-2">
            {Object.entries({
              "symptoms": "Symptoms",
              "previous_history": "Medical History",
              "medication_history": "Medications",
              "additional_symptoms": "Additional Info",
              "diagnosis": "Diagnosis",
              "criticality": "Recommendations"
            }).map(([key, label]) => (
              <div key={key} className="flex items-center gap-2">
                <div className={`w-3 h-3 rounded-full ${
                  ["end", key].includes(currentStep) || 
                  (currentStep === "criticality" && key !== "criticality" && key !== "end") || 
                  (currentStep === "diagnosis" && ["symptoms", "previous_history", "medication_history", "additional_symptoms"].includes(key))
                    ? 'bg-green-500' 
                    : currentStep === key 
                      ? 'bg-blue-500' 
                      : 'bg-gray-300'
                }`}></div>
                <span className={`text-sm ${
                  currentStep === key 
                    ? 'text-blue-700 font-medium' 
                    : 'text-gray-600'
                }`}>{label}</span>
              </div>
            ))}
          </div>
        </div>
        
        {/* Chat history */}
        <div className="mt-4 border-t border-gray-200 pt-4">
          <h3 className="text-gray-700 font-medium flex items-center gap-1.5 mb-2">
            <FiClock className="text-gray-500" />
            <span>Conversation History</span>
          </h3>
          <div className="space-y-1.5 max-h-[200px] overflow-y-auto pr-1">
            {chatHistory.length > 0 ? chatHistory.map((chat, index) => (
              <div
                key={index}
                className="p-2 hover:bg-gray-100 rounded-md cursor-pointer text-gray-600 text-sm flex items-center gap-1.5"
              >
                <FiMessageCircle className="text-gray-400 flex-shrink-0" />
                <span className="truncate">{chat.title}</span>
              </div>
            )) : (
              <p className="text-gray-400 text-sm italic p-2">No previous conversations</p>
            )}
          </div>
        </div>
        
        {/* Generate Summary button */}
        {showSummaryButton && (
          <div className="mt-4 text-center">
            <button
              onClick={generateCaseSummary}
              className="w-full bg-green-600 hover:bg-green-700 text-white px-4 py-2.5 rounded-lg transition-colors shadow-sm flex items-center justify-center gap-2"
            >
              <FiFileText />
              <span>Generate Case Summary</span>
            </button>
          </div>
        )}
        
        {/* New consultation button */}
        {conversationComplete && (
          <button
            onClick={startNewConsultation}
            className="mt-4 w-full bg-blue-600 hover:bg-blue-700 text-white rounded-lg py-2.5 transition-colors shadow-sm flex items-center justify-center gap-2"
          >
            <FiPlus />
            <span>Start New Consultation</span>
          </button>
        )}
      </div>

      {/* Main Chat Area */}
      <div className="flex-1 flex flex-col">
        {/* Chat header */}
        <div className="p-4 border-b border-gray-200 bg-white shadow-sm">
          <div className="max-w-3xl mx-auto flex justify-between items-center">
            <h1 className="text-lg font-semibold text-gray-800 flex items-center gap-2">
              <MdOutlineHealthAndSafety className="text-blue-500" />
              <span>Medical Consultation</span>
            </h1>
            <div className="text-sm text-gray-500 flex items-center gap-1">
              <FiClock className="text-gray-400" />
              <span>Session ID: {userId.substring(0, 8)}</span>
            </div>
          </div>
        </div>
        
        {/* Chat Messages */}
        <div className="flex-1 overflow-y-auto p-6 bg-gray-50">
          <div className="max-w-3xl mx-auto">
            {messages.map((message, index) => renderMessage(message, index))}
            <div ref={messagesEndRef} />
          </div>
        </div>

        {/* Input Area */}
        <div className="border-t border-gray-200 p-4 bg-white">
          <form onSubmit={handleSubmit} className="max-w-3xl mx-auto">
            <div className="flex gap-3">
              <input
                type="text"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                className="flex-1 bg-white text-gray-800 rounded-lg px-4 py-3 focus:outline-none focus:ring-2 focus:ring-blue-500 border border-gray-300 shadow-sm"
                placeholder="Type your message..."
                disabled={conversationComplete}
              />
              <button
                type="submit"
                className={`px-5 py-3 rounded-lg transition-colors shadow-sm flex items-center gap-1.5 ${
                  conversationComplete
                    ? 'bg-gray-200 text-gray-400 cursor-not-allowed'
                    : 'bg-blue-600 hover:bg-blue-700 text-white'
                }`}
                disabled={conversationComplete}
              >
                <FiSend />
                <span>Send</span>
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
};

export default ChatPage; 
