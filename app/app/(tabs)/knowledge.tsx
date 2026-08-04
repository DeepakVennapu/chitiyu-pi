import { View, Text, StyleSheet } from "react-native";

export default function KnowledgeScreen() {
  return (
    <View style={styles.container}>
      <Text style={styles.text}>Knowledge — coming in Task 3</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#000", alignItems: "center", justifyContent: "center" },
  text: { color: "#fff" },
});
