import React, { useRef } from "react";
import { View, Text, Animated, PanResponder, StyleSheet, Alert } from "react-native";
import { useTheme } from "../lib/theme";

interface Props {
  children: React.ReactNode;
  confirmTitle: string;
  confirmMessage: string;
  onDelete: () => void;
  backgroundColor: string;
}

const SWIPE_THRESHOLD = -80;

export function SwipeableRow({
  children,
  confirmTitle,
  confirmMessage,
  onDelete,
  backgroundColor,
}: Props) {
  const { colors } = useTheme();
  const translateX = useRef(new Animated.Value(0)).current;
  const deleteOpacity = translateX.interpolate({
    inputRange: [SWIPE_THRESHOLD, 0],
    outputRange: [1, 0],
    extrapolate: "clamp",
  });

  const panResponder = PanResponder.create({
    onMoveShouldSetPanResponder: (_, { dx }) => Math.abs(dx) > 10,
    onPanResponderMove: (_, { dx }) => { if (dx < 0) translateX.setValue(dx); },
    onPanResponderRelease: (_, { dx }) => {
      if (dx < SWIPE_THRESHOLD) {
        Alert.alert(confirmTitle, confirmMessage, [
          { text: "Cancel", onPress: () => resetPosition() },
          {
            text: "Delete",
            onPress: () => onDelete(),
            style: "destructive",
          },
        ]);
      } else {
        resetPosition();
      }
    },
  });

  const resetPosition = () => {
    Animated.spring(translateX, { toValue: 0, useNativeDriver: true }).start();
  };

  return (
    <View style={styles.container}>
      <Animated.View style={[styles.deleteBackground, { opacity: deleteOpacity, backgroundColor: colors.swipeDelete }]}>
        <Text style={styles.deleteLabel}>Delete</Text>
      </Animated.View>
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
  deleteBackground: { position: "absolute", right: 0, top: 0, bottom: 0, width: 120, alignItems: "center", justifyContent: "center" },
  deleteLabel: { color: "#fff", fontWeight: "600", fontSize: 14 },
  row: { flexDirection: "row", alignItems: "center" },
});
