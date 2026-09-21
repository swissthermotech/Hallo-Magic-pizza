import React, { useState } from "react";
import { ActivityIndicator, Alert, Linking, Platform, Pressable, Text, View } from "react-native";
import { Image } from "expo-image";
import * as ImagePicker from "expo-image-picker";
import { Feather } from "@react-native-vector-icons/feather";
import { makeStyles, useTheme } from "@/src/theme";
import { useI18n } from "@/src/i18n";
import { imgUri, uploadProductPhoto } from "@/src/api";
import { Button, FONT_TEXT, useToast } from "@/src/components/ui";

interface Props {
  main: string | null;
  extra: string[];
  onChange: (main: string | null, extra: string[]) => void;
}

/**
 * Admin photo manager: main photo + additional photos.
 * Photos are uploaded (and optimised server-side) immediately so the admin can preview them;
 * they are only attached to the product when the editor's "Save" is pressed.
 */
export function PhotoManager({ main, extra, onChange }: Props) {
  const styles = useStyles();
  const { colors } = useTheme();
  const { t } = useI18n();
  const toast = useToast();
  const [busy, setBusy] = useState<"main" | "extra" | null>(null);

  const ensurePermission = async (): Promise<boolean> => {
    if (Platform.OS === "web") return true;
    const cur = await ImagePicker.getMediaLibraryPermissionsAsync();
    if (cur.granted) return true;
    if (cur.canAskAgain) {
      const res = await ImagePicker.requestMediaLibraryPermissionsAsync();
      if (res.granted) return true;
      if (res.canAskAgain) return false;
    }
    Alert.alert(t("photoPermissionTitle"), t("photoPermissionBody"), [
      { text: t("close"), style: "cancel" },
      { text: t("openSettings"), onPress: () => Linking.openSettings() },
    ]);
    return false;
  };

  const pick = async (target: "main" | "extra") => {
    if (!(await ensurePermission())) return;
    const res = await ImagePicker.launchImageLibraryAsync({ mediaTypes: ["images"], quality: 1, allowsMultipleSelection: target === "extra", selectionLimit: 6 });
    if (res.canceled || !res.assets.length) return;
    setBusy(target);
    try {
      const urls: string[] = [];
      for (const a of res.assets) {
        const up = await uploadProductPhoto(a.uri, a.fileName || "photo.jpg", a.mimeType || "image/jpeg", a.width, a.height);
        urls.push(up.url);
      }
      if (target === "main") onChange(urls[0], extra);
      else onChange(main, [...extra, ...urls]);
      toast.show(t("saved"), "success");
    } catch (e: any) {
      toast.show(`${t("uploadError")}: ${e?.message || "?"}`, "error");
    } finally {
      setBusy(null);
    }
  };

  const removeExtra = (u: string) => onChange(main, extra.filter((x) => x !== u));
  const setAsMain = (u: string) => onChange(u, [...(main ? [main] : []), ...extra.filter((x) => x !== u)]);

  return (
    <View style={{ gap: 12 }}>
      {/* Main photo */}
      <Text style={styles.label}>{t("mainPhoto")}</Text>
      <View style={styles.mainWrap} testID="photo-main">
        {main ? <Image source={{ uri: imgUri(main) }} style={styles.mainImg} contentFit="cover" transition={200} /> : (
          <View style={styles.placeholder}><Feather name="image" size={36} color={colors.muted} /></View>
        )}
        {busy === "main" ? <View style={styles.busy}><ActivityIndicator color={colors.onSurfaceInverse} /><Text style={styles.busyText}>{t("uploading")}</Text></View> : null}
      </View>
      <View style={styles.row}>
        <Button title={main ? t("replacePhoto") : t("addPhoto")} icon={main ? "refresh-cw" : "camera"} variant="secondary" onPress={() => pick("main")} disabled={!!busy} style={{ flex: 1 }} testID="photo-main-pick" />
        {main ? <Button title={t("removePhoto")} icon="trash-2" variant="outline" onPress={() => onChange(null, extra)} disabled={!!busy} style={{ flex: 1 }} testID="photo-main-remove" /> : null}
      </View>

      {/* Additional photos */}
      <Text style={styles.label}>{t("additionalPhotos")} ({extra.length})</Text>
      <View style={styles.grid}>
        {extra.map((u) => (
          <View key={u} style={styles.thumbWrap} testID={`photo-extra-${extra.indexOf(u)}`}>
            <Image source={{ uri: imgUri(u) }} style={styles.thumb} contentFit="cover" />
            <View style={styles.thumbActions}>
              <Pressable onPress={() => setAsMain(u)} style={styles.thumbBtn} testID={`photo-extra-main-${extra.indexOf(u)}`}><Feather name="star" size={14} color={colors.onSurfaceInverse} /></Pressable>
              <Pressable onPress={() => removeExtra(u)} style={styles.thumbBtn} testID={`photo-extra-remove-${extra.indexOf(u)}`}><Feather name="x" size={14} color={colors.onSurfaceInverse} /></Pressable>
            </View>
          </View>
        ))}
        <Pressable onPress={() => pick("extra")} disabled={!!busy} style={styles.addTile} testID="photo-extra-add">
          {busy === "extra" ? <ActivityIndicator color={colors.brandPrimary} /> : <Feather name="plus" size={24} color={colors.brandPrimary} />}
        </Pressable>
      </View>
      <Text style={styles.hint}>{t("photoHint")}</Text>
    </View>
  );
}

const useStyles = makeStyles((colors) => ({
  label: { fontFamily: FONT_TEXT, fontSize: 13, fontWeight: "600", color: colors.muted, textTransform: "uppercase", letterSpacing: 0.6 },
  mainWrap: { width: "100%", height: 200, borderRadius: 16, overflow: "hidden", backgroundColor: colors.surfaceTertiary },
  mainImg: { width: "100%", height: "100%" },
  placeholder: { flex: 1, alignItems: "center", justifyContent: "center" },
  busy: { position: "absolute", left: 0, right: 0, top: 0, bottom: 0, backgroundColor: colors.overlay, alignItems: "center", justifyContent: "center", gap: 8 },
  busyText: { fontFamily: FONT_TEXT, fontSize: 13, fontWeight: "700", color: colors.onSurfaceInverse },
  row: { flexDirection: "row", gap: 10 },
  grid: { flexDirection: "row", flexWrap: "wrap", gap: 10 },
  thumbWrap: { width: 96, height: 96, borderRadius: 12, overflow: "hidden", backgroundColor: colors.surfaceTertiary },
  thumb: { width: "100%", height: "100%" },
  thumbActions: { position: "absolute", right: 4, top: 4, flexDirection: "row", gap: 4 },
  thumbBtn: { width: 28, height: 28, borderRadius: 14, backgroundColor: colors.overlay, alignItems: "center", justifyContent: "center" },
  addTile: { width: 96, height: 96, borderRadius: 12, borderWidth: 1.5, borderStyle: "dashed", borderColor: colors.borderStrong, alignItems: "center", justifyContent: "center", backgroundColor: colors.surfaceSecondary },
  hint: { fontFamily: FONT_TEXT, fontSize: 12, color: colors.muted },
}));
