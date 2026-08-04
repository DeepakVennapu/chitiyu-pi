import { Tabs } from "expo-router";
import { Ionicons } from "@expo/vector-icons";

type IoniconsName = React.ComponentProps<typeof Ionicons>["name"];

interface TabConfig {
  name: string;
  title: string;
  icon: IoniconsName;
  activeIcon: IoniconsName;
}

const TABS: TabConfig[] = [
  { name: "index", title: "Insights", icon: "bulb-outline", activeIcon: "bulb" },
  { name: "health", title: "Health", icon: "heart-outline", activeIcon: "heart" },
  { name: "finance", title: "Finance", icon: "wallet-outline", activeIcon: "wallet" },
  { name: "tasks", title: "Tasks", icon: "checkbox-outline", activeIcon: "checkbox" },
  { name: "knowledge", title: "Knowledge", icon: "library-outline", activeIcon: "library" },
];

export default function RootLayout() {
  return (
    <Tabs
      screenOptions={{
        tabBarActiveTintColor: "#007AFF",
        tabBarInactiveTintColor: "#8E8E93",
        tabBarStyle: { backgroundColor: "#000", borderTopColor: "#1C1C1E" },
        headerStyle: { backgroundColor: "#000" },
        headerTintColor: "#fff",
        headerTitleStyle: { fontWeight: "600" },
      }}
    >
      {TABS.map((tab) => (
        <Tabs.Screen
          key={tab.name}
          name={tab.name}
          options={{
            title: tab.title,
            tabBarIcon: ({ focused, color, size }) => (
              <Ionicons
                name={focused ? tab.activeIcon : tab.icon}
                size={size}
                color={color}
              />
            ),
          }}
        />
      ))}
    </Tabs>
  );
}
