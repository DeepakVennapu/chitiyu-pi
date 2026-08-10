import React, { useRef } from "react";
import { View, Text, Animated, PanResponder, Platform, StyleSheet, TouchableOpacity, Alert } from "react-native";
import { useTheme } from "../lib/theme";

interface Props {
  children: React.ReactNode;
  confirmTitle: string;
  confirmMessage: string;
  onDelete: () => void;
  backgroundColor: string;
}

const REVEAL_WIDTH = 80;
const SWIPE_THRESHOLD = -50;

export function SwipeableRow({
  children,
  confirmTitle,
  confirmMessage,
  onDelete,
  backgroundColor,
}: Props) {
  const { colors } = useTheme();

  // Web: PanResponder is a no-op — just render children, no swipe chrome
  if (Platform.OS === "web") {
    return <View style={{ backgroundColor }}>{children}</View>;
  }
  const translateX = useRef(new Animated.Value(0)).current;
  const revealedRef = useRef(false);

  const snapTo = (toValue: number) => {
    revealedRef.current = toValue < 0;
    Animated.spring(translateX, { toValue, useNativeDriver: true, bounciness: 0 }).start();
  };

  const panResponder = useRef(PanResponder.create({
    onMoveShouldSetPanResponder: (_, { dx, dy }) =>
      Math.abs(dx) > 8 && Math.abs(dx) > Math.abs(dy),
    onPanResponderGrant: () => {
      translateX.stopAnimation();
    },
    onPanResponderMove: (_, { dx }) => {
      const base = revealedRef.current ? -REVEAL_WIDTH : 0;
      const next = base + dx;
      if (next <= 0) translateX.setValue(Math.max(next, -REVEAL_WIDTH));
    },
    onPanResponderRelease: (_, { dx }) => {
      if (revealedRef.current) {
        if (dx > 20) snapTo(0);
        else snapTo(-REVEAL_WIDTH);
      } else {
        if (dx < SWIPE_THRESHOLD) snapTo(-REVEAL_WIDTH);
        else snapTo(0);
      }
    },
  })).current;

  const handleDeletePress = () => {
    Alert.alert(confirmTitle, confirmMessage, [
      { text: "Cancel", style: "cancel", onPress: () => snapTo(0) },
      { text: "Delete", style: "destructive", onPress: () => { snapTo(0); onDelete(); } },
    ]);
  };

  return (
    <View style={styles.container}>
      <TouchableOpacity
        style={[styles.deleteBackground, { backgroundColor: colors.swipeDelete }]}
        onPress={handleDeletePress}
        activeOpacity={0.8}
      >
        <Text style={styles.deleteLabel}>Delete</Text>
      </TouchableOpacity>
      <Animated.View
        style={[styles.row, { transform: [{ translateX }], backgroundColor }]}
        {...panResponder.panHandlers}
      >
        {children}
      </Animated.View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { position: "relative", overflow: "hidden" },
  deleteBackground: {
    position: "absolute", right: 0, top: 0, bottom: 0, width: REVEAL_WIDTH,
    alignItems: "center", justifyContent: "center",
  },
  deleteLabel: { color: "#fff", fontWeight: "600", fontSize: 14 },
  row: { flexDirection: "row", alignItems: "center" },
});
