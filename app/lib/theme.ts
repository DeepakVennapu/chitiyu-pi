import { useColorScheme } from "react-native";

export interface Colors {
  background: string;       // page background
  card: string;             // card/sheet background
  cardElevated: string;     // slightly elevated card (modals)
  border: string;           // hairline separator
  borderSubtle: string;     // slightly more visible border
  text: string;             // primary text
  textSecondary: string;    // muted text
  textTertiary: string;     // very muted / placeholder
  accent: string;           // blue primary action
  accentGreen: string;      // success / calorie green
  accentOrange: string;     // warning / calorie orange
  accentPurple: string;     // carbs
  accentRed: string;        // error / overbudget
  tabBar: string;           // tab bar background
  inputBg: string;          // text input background
  checkCircle: string;      // task checkbox border
  overdueStripe: string;    // overdue section left border bg
  swipeDelete: string;      // swipe delete background
}

const dark: Colors = {
  background: "#000000",
  card: "#1C1C1E",
  cardElevated: "#2C2C2E",
  border: "#2C2C2E",
  borderSubtle: "#3A3A3C",
  text: "#FFFFFF",
  textSecondary: "#8E8E93",
  textTertiary: "#636366",
  accent: "#007AFF",
  accentGreen: "#30D158",
  accentOrange: "#FF9F0A",
  accentPurple: "#BF5AF2",
  accentRed: "#FF453A",
  tabBar: "#000000",
  inputBg: "#2C2C2E",
  checkCircle: "#636366",
  overdueStripe: "#1C0A0A",
  swipeDelete: "#FF453A",
};

const light: Colors = {
  background: "#F2F2F7",
  card: "#FFFFFF",
  cardElevated: "#F2F2F7",
  border: "#C6C6C8",
  borderSubtle: "#D1D1D6",
  text: "#000000",
  textSecondary: "#3C3C43CC",
  textTertiary: "#3C3C4399",
  accent: "#007AFF",
  accentGreen: "#34C759",
  accentOrange: "#FF9500",
  accentPurple: "#AF52DE",
  accentRed: "#FF3B30",
  tabBar: "#F9F9F9",
  inputBg: "#FFFFFF",
  checkCircle: "#C7C7CC",
  overdueStripe: "#FFF1F0",
  swipeDelete: "#FF3B30",
};

export function useTheme(): { colors: Colors; isDark: boolean } {
  const scheme = useColorScheme();
  const isDark = scheme === "dark";
  return { colors: isDark ? dark : light, isDark };
}
