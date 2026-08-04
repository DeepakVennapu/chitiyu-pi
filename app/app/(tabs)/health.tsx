import { View, Text, StyleSheet } from "react-native";

export default function HealthScreen() {
  return (
    <View style={styles.container}>
      <Text style={styles.text}>Health — coming in Task 3</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#000", alignItems: "center", justifyContent: "center" },
  text: { color: "#fff" },
});
