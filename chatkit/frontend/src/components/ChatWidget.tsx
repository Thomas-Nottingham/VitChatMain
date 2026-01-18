

import React from "react";
import { ChatKit, useChatKit } from "@openai/chatkit-react";
import { CHATKIT_API_DOMAIN_KEY, CHATKIT_API_URL } from "../lib/config";

export function ChatWidget() {
  const [message, setMessage] = React.useState("");

  const { control, sendUserMessage } = useChatKit({
    api: {
      url: CHATKIT_API_URL,
      domainKey: CHATKIT_API_DOMAIN_KEY,
    },

    widgets: {
      onAction: async (action: any) => {
        if (action.type === "open.url") {
          const url = action.payload?.url;
          if (url) {
            window.open(url, "_blank", "noopener,noreferrer");
          }
        }
      },
    },

    history: {
      enabled: false
    },

    composer: {
      attachments: { enabled: false },
      placeholder: "Type your question here...",
    },

    startScreen: {
      greeting: "Welcome to Inspitalfields ask me any questions about products or services",

    },

    theme: {
      density: "spacious",
      colorScheme: "light",
      color: {
        grayscale: { hue: 210, tint: 5, shade: 3 }, // Cool blue-gray instead of warm tan
        accent: { primary: "#000000ff", level: 2 }, // Rich bronze/gold to match your ornate V logo
      },
      radius: "round",
    },

    threadItemActions: {
      feedback: false,
    },
    } as any);

  const sendMessage = () => {
    if (!message.trim()) return;
    sendUserMessage({ text: message });
    setMessage("");
  };

  return (
    <div className="fixed inset-0 w-screen h-screen bg-[#fbf7f2] flex flex-col">
      {/* Chat body */}
      <div className="flex-1 overflow-hidden relative">
        <ChatKit control={control} className="h-full w-full" />

        {/* Custom Input Bar */}

      </div>
    </div>
  );
}
