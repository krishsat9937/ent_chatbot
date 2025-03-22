import { useState } from "react";
import Message from "./Message";
import Loader from "./Loader";

const API_URL = "http://localhost:8000/chat"; // Update if hosted

const Chat = () => {
    const [messages, setMessages] = useState<{ role: string; content: string }[]>([]);
    const [userInput, setUserInput] = useState("");
    const [loading, setLoading] = useState(false);

    const sendMessage = async () => {
        if (!userInput.trim()) return;

        const userMessage = { role: "user", content: userInput };
        setMessages((prev) => [...prev, userMessage]);
        setUserInput("");
        setLoading(true);

        try {
            const response = await fetch(API_URL, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ text: userInput }),
            });

            if (!response.body) {
                throw new Error("No response body from server.");
            }

            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let newContent = "";
            let toolCallArgs = ""; // Store tool call argument construction

            let botMessage = { role: "bot", content: "" };
            setMessages((prev) => [...prev, botMessage]); // Add an empty bot message

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;

                const chunk = decoder.decode(value, { stream: true });

                chunk.split("\n").forEach((line) => {
                    if (line.startsWith("data: ")) {
                        const data = line.replace("data: ", "").trim();
                        if (data === "[DONE]") return;

                        try {
                            const parsed = JSON.parse(data);

                            // 🔹 Handle regular messages
                            if (parsed.content) {
                                newContent += parsed.content;
                                setMessages((prev) => {
                                    const updatedMessages = [...prev];
                                    updatedMessages[updatedMessages.length - 1].content = newContent;
                                    return [...updatedMessages];
                                });
                            }

                            // 🔹 Handle tool calls (function calls)
                            if (parsed.tool_calls) {
                                parsed.tool_calls.forEach((toolCall: any) => {
                                    if (toolCall.function?.arguments) {
                                        toolCallArgs += toolCall.function.arguments;
                                    }
                                });

                                setMessages((prev) => {
                                    const updatedMessages = [...prev];
                                    updatedMessages[updatedMessages.length - 1].content = `Processing: ${toolCallArgs}`;
                                    return [...updatedMessages];
                                });
                            }

                            // 🔹 Handle final tool response (like extracted diseases)
                            if (parsed.toolResponse) {
                                setMessages((prev) => [
                                    ...prev,
                                    { role: "bot", content: `Detected diseases: ${parsed.toolResponse}` },
                                ]);
                            }
                        } catch (error) {
                            console.error("Error parsing JSON:", error);
                        }
                    }
                });
            }
        } catch (error) {
            console.error("Streaming error:", error);
            setMessages((prev) => [...prev, { role: "bot", content: "Error fetching response." }]);
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="flex flex-col h-screen bg-gray-100 dark:bg-gray-900 p-4">
            <div className="flex-grow overflow-y-auto p-2 space-y-2">
                {messages.map((msg, index) => (
                    <Message key={index} role={msg.role} content={msg.content} />
                ))}
                {loading && <Loader />}
            </div>
            <div className="flex p-2 border-t bg-white dark:bg-gray-800">
                <input
                    type="text"
                    className="flex-grow p-2 border rounded-lg dark:text-white dark:bg-gray-700"
                    value={userInput}
                    onChange={(e) => setUserInput(e.target.value)}
                    onKeyDown={(e) => e.key === "Enter" && sendMessage()}
                    placeholder="Ask a medical question..."
                />
                <button
                    className="ml-2 bg-blue-500 text-white px-4 py-2 rounded-lg hover:bg-blue-600"
                    onClick={sendMessage}
                    disabled={loading}
                >
                    Send
                </button>
            </div>
        </div>
    );
};

export default Chat;