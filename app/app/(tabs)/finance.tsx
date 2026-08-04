import { View, Text, StyleSheet } from "react-native";

export default function FinanceScreen() {
  return (
    <View style={styles.container}>
      <Text style={styles.text}>Finance — coming in Task 3</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#000", alignItems: "center", justifyContent: "center" },
  text: { color: "#fff" },
});
