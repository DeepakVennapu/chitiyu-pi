import React, { useRef, useState } from "react";
import { Alert, Animated, PanResponder, StyleSheet, Text, View } from "react-native";
import { useTheme } from "../lib/theme";

const DELETE_WIDTH = 80;

interface Props {
  confirmTitle?: string;
  confirmMessage?: string;
  onDelete: () => void;
  backgroundColor: string;  // caller passes colors.card or colors.background
  children: React.ReactNode;
}

export function SwipeableRow({ confirmTitle = "Delete?", confirmMessage, onDelete, backgroundColor, children }: Props) {
  const { colors } = useTheme();
  const translateX = useRef(new Animated.Value(0)).current;
  const [open, setOpen] = useState(false);

  const snapOpen = () => {
    setOpen(true);
    Animated.spring(translateX, { toValue: -DELETE_WIDTH, useNativeDriver: true, bounciness: 0 }).start();
  };

  const snapClose = () => {
    setOpen(false);
    Animated.spring(translateX, { toValue: 0, useNativeDriver: true, bounciness: 4 }).start();
  };

  const panResponder = PanResponder.create({
    onMoveShouldSetPanResponder: (_, { dx, dy }) =>
      Math.abs(dx) > 8 && Math.abs(dx) > Math.abs(dy),
    onPanResponderMove: (_, { dx }) => {
      const base = open ? -DELETE_WIDTH : 0;
      translateX.setValue(Math.max(-DELETE_WIDTH * 1.1, Math.min(0, base + dx)));
    },
    onPanResponderRelease: (_, { dx }) => {
      if (!open && dx < -DELETE_WIDTH * 0.4) snapOpen();
      else if (open && dx > DELETE_WIDTH * 0.3) snapClose();
      else if (open) snapOpen();
      else snapClose();
    },
  });

  const handleDeletePress = () => {
    Alert.alert(confirmTitle, confirmMessage, [
      { text: "Cancel", style: "cancel", onPress: snapClose },
      {
        text: "Delete", style: "destructive",
        onPress: () => {
          Animated.timing(translateX, { toValue: -400, duration: 200, useNativeDriver: true }).start(onDelete);
        },
      },
    ]);
  };

  return (
    <View style={styles.wrapper}>
      <View style={[styles.deleteAction, { backgroundColor: colors.swipeDelete }]}>
        <Text style={styles.deleteLabel} onPress={handleDeletePress}>Delete</Text>
      </View>
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
  wrapper: { overflow: "hidden" },
  deleteAction: {
    position: "absolute", right: 0, top: 0, bottom: 0, width: DELETE_WIDTH,
    alignItems: "center", justifyContent: "center",
  },
  deleteLabel: { color: "#fff", fontWeight: "700", fontSize: 13 },
  row: { flexDirection: "row" },
});
