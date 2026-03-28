import { MessageCircle, Send } from 'lucide-react';

const TelegramWidget = () => {
  return (
    <div className="fixed bottom-6 right-6 z-50 animate-fade-up">
      <div className="relative group flex items-center justify-center">
        {/* Tooltip */}
        <div className="absolute right-full mr-5 mb-0 w-max bg-card/90 backdrop-blur-md border border-border/50 px-4 py-2.5 rounded-xl shadow-xl shadow-black/20 opacity-0 translate-x-2 group-hover:opacity-100 group-hover:translate-x-0 transition-all duration-300 pointer-events-none flex items-center gap-2">
          <span className="relative flex h-2 w-2">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-[#2AABEE] opacity-75"></span>
            <span className="relative inline-flex rounded-full h-2 w-2 bg-[#2AABEE]"></span>
          </span>
          <p className="text-sm font-medium text-foreground">Chat with TruthCrew Bot</p>
          {/* Tooltip arrow */}
          <div className="absolute top-1/2 -right-1.5 -translate-y-1/2 w-3 h-3 bg-card/90 border-r border-t border-border/50 transform rotate-45"></div>
        </div>

        {/* Pulse effect ring */}
        <div className="absolute inset-0 bg-[#2AABEE] rounded-full animate-pulse-ring opacity-40"></div>
        
        {/* Button */}
        <a 
          href="https://t.me/Truth_Crew_Bot" 
          target="_blank" 
          rel="noopener noreferrer"
          className="relative flex items-center justify-center w-14 h-14 bg-gradient-to-tr from-[#229ED9] to-[#2AABEE] text-white rounded-full shadow-lg shadow-[#229ED9]/40 transition-all duration-300 hover:scale-110 active:scale-95 group-hover:shadow-[0_0_30px_rgba(34,158,217,0.6)]"
          aria-label="Open Telegram Bot"
        >
          {/* Telegram-style path or custom icon. We use lucide's Send that looks like paperplane */}
          <Send className="w-6 h-6 ml-[-2px] mt-[2px] transform -rotate-12 fill-white text-white" />
        </a>
      </div>
    </div>
  );
};

export default TelegramWidget;
