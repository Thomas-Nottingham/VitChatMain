
import React from "react";
import { ChatKit, useChatKit } from "@openai/chatkit-react";
import { CHATKIT_API_DOMAIN_KEY, CHATKIT_API_URL } from "../lib/config";

const CMS_URL = "http://localhost:8001";

export function ChatWidget() {
  const [appearance, setAppearance] = React.useState<any>(null);

  // Fetch appearance config from CMS on load
  React.useEffect(() => {
    fetch(`${CMS_URL}/api/appearance`)
      .then(r => r.json())
      .then(setAppearance)
      .catch(() => {
        // Fall back to defaults if CMS is unreachable
        setAppearance({
          accentColor: "#000000",
          colorScheme: "light",
          radius: "round",
          density: "spacious",
          hue: 210,
          tint: 5,
          shade: 3,
          botName: "Inspitalfields",
          greeting: "Welcome to Inspitalfields — ask me anything about our products or services!",
          placeholder: "Type your question here...",
        });
      });
  }, []);

  const { control } = useChatKit({
    api: {
      url: CHATKIT_API_URL,
      domainKey: CHATKIT_API_DOMAIN_KEY,
    },
    widgets: {
      onAction: async (action: any) => {
        if (action.type === "open.url") {
          const url = action.payload?.url;
          if (url) window.open(url, "_blank", "noopener,noreferrer");
        }
      },
    },
    history: { enabled: false },
    composer: {
      attachments: { enabled: false },
      placeholder: appearance?.placeholder ?? "Type your question here...",
    },
    startScreen: {
      greeting: appearance?.greeting ?? "Welcome! Ask me anything.",
    },
    theme: {
      density: appearance?.density ?? "spacious",
      colorScheme: appearance?.colorScheme ?? "light",
      color: {
        grayscale: {
          hue: appearance?.hue ?? 210,
          tint: appearance?.tint ?? 5,
          shade: appearance?.shade ?? 3
        },
        accent: { primary: appearance?.accentColor ?? "#000000", level: 2 },
      },
      radius: appearance?.radius ?? "round",
    },
    threadItemActions: { feedback: false },
  } as any);

  if (!appearance) return <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100vh' }}>Loading...</div>;

  return (
    <div className="fixed inset-0 w-screen h-screen bg-[#fbf7f2] flex flex-col">
      <div className="flex-1 overflow-hidden relative">
        <ChatKit control={control} className="h-full w-full" />
      </div>
    </div>
  );
}