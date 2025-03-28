import { useNavigate } from 'react-router-dom';

const LandingPage = () => {
  const navigate = useNavigate();

  return (
    <div className="min-h-screen bg-gradient-to-b from-gray-900 to-gray-800">
      <div className="container mx-auto px-6 py-16">
        <nav className="flex justify-between items-center mb-16">
          <h1 className="text-2xl font-bold text-white">MedBot</h1>
          <button
            onClick={() => navigate('/chat')}
            className="bg-blue-600 hover:bg-blue-700 text-white px-6 py-2 rounded-full transition-all"
          >
            Try MedBot
          </button>
        </nav>

        <div className="max-w-4xl mx-auto text-center">
          <h2 className="text-5xl font-bold text-white mb-8">
            Your Personal Medical Assistant
          </h2>
          <p className="text-xl text-gray-300 mb-12">
            Get instant medical guidance and symptom assessment through our advanced AI-powered chatbot
          </p>

          <div className="grid md:grid-cols-3 gap-8 mb-16">
            {features.map((feature, index) => (
              <div key={index} className="bg-gray-800 p-6 rounded-xl">
                <div className="text-blue-500 text-2xl mb-4">{feature.icon}</div>
                <h3 className="text-xl font-semibold text-white mb-2">{feature.title}</h3>
                <p className="text-gray-400">{feature.description}</p>
              </div>
            ))}
          </div>

          <button
            onClick={() => navigate('/chat')}
            className="bg-blue-600 hover:bg-blue-700 text-white text-lg px-8 py-3 rounded-full transition-all"
          >
            Start Your Consultation
          </button>
        </div>
      </div>
    </div>
  );
};

const features = [
  {
    icon: "🏥",
    title: "24/7 Availability",
    description: "Get medical guidance anytime, anywhere with our always-available chatbot"
  },
  {
    icon: "🤖",
    title: "AI-Powered Analysis",
    description: "Advanced symptom analysis using cutting-edge artificial intelligence"
  },
  {
    icon: "📋",
    title: "Medical History Tracking",
    description: "Keep track of your medical history and previous consultations"
  }
];

export default LandingPage; 