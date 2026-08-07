import { Tabs } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import { useTheme } from "../lib/theme";

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
  const { colors } = useTheme();
  return (
    <Tabs
      screenOptions={{
        tabBarActiveTintColor: colors.accent,
        tabBarInactiveTintColor: colors.textSecondary,
        tabBarStyle: { backgroundColor: colors.tabBar, borderTopColor: colors.border },
        headerStyle: { backgroundColor: colors.background },
        headerTintColor: colors.text,
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
              <Ionicons name={focused ? tab.activeIcon : tab.icon} size={size} color={color} />
            ),
          }}
        />
      ))}
    </Tabs>
  );
}
