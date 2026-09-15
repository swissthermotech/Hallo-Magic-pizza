import { QueryClientProvider } from "@tanstack/react-query";
import { Stack } from "expo-router";
import { LogBox, View, ActivityIndicator } from "react-native";
import { useFonts } from "expo-font";
import { StatusBar } from "expo-status-bar";
import { GestureHandlerRootView } from "react-native-gesture-handler";
import { SafeAreaProvider } from "react-native-safe-area-context";
import { KeyboardProvider } from "react-native-keyboard-controller";

import { ErrorBoundary } from "@/src/components/error-boundary";
import { queryClient } from "@/src/query-client";
import { LanguageProvider } from "@/src/i18n";
import { CartProvider } from "@/src/cart";
import { StaffProvider } from "@/src/staff-auth";
import { ToastProvider } from "@/src/components/ui";
import { themes } from "@/src/theme";

// Disable logbox errors etc so that users can see the app
// and agent works as expected.
LogBox.ignoreAllLogs(true);

export default function RootLayout() {
  // Prewarm icon + brand fonts so glyphs render on first paint (Expo Go Android fix).
  const [fontsLoaded] = useFonts({
    PlayfairDisplay: require("../assets/fonts/PlayfairDisplay.ttf"),
    DMSans: require("../assets/fonts/DMSans.ttf"),
    Feather: require("@react-native-vector-icons/feather/fonts/Feather.ttf"),
  });

  if (!fontsLoaded) {
    return (
      <View style={{ flex: 1, alignItems: "center", justifyContent: "center", backgroundColor: themes.light.surface }}>
        <ActivityIndicator color={themes.light.brandPrimary} />
      </View>
    );
  }

  // One app level ErrorBoundary; a render crash shows a reload screen
  // instead of a blank app.
  return (
    <ErrorBoundary>
      <QueryClientProvider client={queryClient}>
        <GestureHandlerRootView style={{ flex: 1 }}>
          <SafeAreaProvider>
            <KeyboardProvider>
              <LanguageProvider>
                <CartProvider>
                  <StaffProvider>
                  <ToastProvider>
                    <StatusBar style="dark" />
                    <Stack screenOptions={{ headerShown: false, contentStyle: { backgroundColor: themes.light.surface } }}>
                      <Stack.Screen name="(tabs)" />
                      <Stack.Screen name="product/[id]" options={{ presentation: "modal" }} />
                      <Stack.Screen name="checkout" />
                      <Stack.Screen name="order/[id]" />
                      <Stack.Screen name="staff" />
                    </Stack>
                  </ToastProvider>
                  </StaffProvider>
                </CartProvider>
              </LanguageProvider>
            </KeyboardProvider>
          </SafeAreaProvider>
        </GestureHandlerRootView>
      </QueryClientProvider>
    </ErrorBoundary>
  );
}
