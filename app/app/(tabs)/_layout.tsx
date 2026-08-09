import React, { useState } from "react";
import { View, TouchableOpacity, Text, StyleSheet } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { Tabs } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import { useTheme } from "../../lib/theme";
import { SmartInputSheet } from "../../components/SmartInputSheet";

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

const TAB_BAR_HEIGHT = 49; // standard iOS tab bar height

export default function TabsLayout() {
  const { colors } = useTheme();
  const insets = useSafeAreaInsets();
  const [fabOpen, setFabOpen] = useState(false);

  const fabBottom = insets.bottom + TAB_BAR_HEIGHT + 16;

  return (
    <View style={{ flex: 1 }}>
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

      {/* FAB — always global, no domainLock */}
      <TouchableOpacity
        style={[s.fab, { backgroundColor: colors.accent, bottom: fabBottom }]}
        onPress={() => setFabOpen(true)}
        activeOpacity={0.85}
      >
        <Text style={s.fabIcon}>+</Text>
      </TouchableOpacity>

      <SmartInputSheet
        visible={fabOpen}
        onClose={() => setFabOpen(false)}
        onConfirmed={() => setFabOpen(false)}
      />
    </View>
  );
}

const s = StyleSheet.create({
  fab: {
    position: "absolute",
    right: 20,
    width: 56,
    height: 56,
    borderRadius: 28,
    alignItems: "center",
    justifyContent: "center",
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.3,
    shadowRadius: 6,
    elevation: 8,
  },
  fabIcon: { color: "#fff", fontSize: 28, fontWeight: "300", lineHeight: 32 },
});
