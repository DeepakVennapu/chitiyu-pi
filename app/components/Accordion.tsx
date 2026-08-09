import React, { useRef, useState } from "react";
import {
  Animated, Easing, LayoutAnimation, Platform,
  StyleSheet, Text, TouchableOpacity, UIManager, View,
} from "react-native";
import { useTheme } from "../lib/theme";

if (Platform.OS === "android") {
  UIManager.setLayoutAnimationEnabledExperimental?.(true);
}

interface AccordionProps {
  title: string;
  badge?: string;        // small label on the right before the chevron (e.g. "$12,400")
  badgeColor?: string;   // override badge text color
  defaultOpen?: boolean;
  children: React.ReactNode;
}

export function Accordion({ title, badge, badgeColor, defaultOpen = false, children }: AccordionProps) {
  const { colors } = useTheme();
  const [open, setOpen] = useState(defaultOpen);
  const rotation = useRef(new Animated.Value(defaultOpen ? 1 : 0)).current;

  const toggle = () => {
    LayoutAnimation.configureNext(LayoutAnimation.Presets.easeInEaseOut);
    Animated.timing(rotation, {
      toValue: open ? 0 : 1,
      duration: 200,
      easing: Easing.out(Easing.quad),
      useNativeDriver: true,
    }).start();
    setOpen((v) => !v);
  };

  const chevronRotate = rotation.interpolate({
    inputRange: [0, 1],
    outputRange: ["0deg", "90deg"],
  });

  return (
    <View style={[styles.container, { backgroundColor: colors.card }]}>
      <TouchableOpacity style={styles.header} onPress={toggle} activeOpacity={0.7}>
        <Text style={[styles.title, { color: colors.text }]}>{title}</Text>
        <View style={styles.right}>
          {badge != null && (
            <Text style={[styles.badge, { color: badgeColor ?? colors.textSecondary }]}>
              {badge}
            </Text>
          )}
          <Animated.Text
            style={[styles.chevron, { color: colors.textTertiary, transform: [{ rotate: chevronRotate }] }]}
          >
            ›
          </Animated.Text>
        </View>
      </TouchableOpacity>
      {open && <View style={[styles.body, { borderTopColor: colors.border }]}>{children}</View>}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { borderRadius: 12, marginBottom: 12, overflow: "hidden" },
  header: {
    flexDirection: "row", alignItems: "center", justifyContent: "space-between",
    paddingHorizontal: 16, paddingVertical: 14,
  },
  title: { fontSize: 15, fontWeight: "600" },
  right: { flexDirection: "row", alignItems: "center", gap: 8 },
  badge: { fontSize: 13, fontWeight: "500" },
  chevron: { fontSize: 20, fontWeight: "400", lineHeight: 22 },
  body: { borderTopWidth: StyleSheet.hairlineWidth, paddingHorizontal: 16, paddingBottom: 12 },
});
