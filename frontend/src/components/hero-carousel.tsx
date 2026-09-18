import React, { useEffect, useRef, useState } from "react";
import { Pressable, ScrollView, useWindowDimensions, View } from "react-native";
import { Image } from "expo-image";
import { makeStyles } from "@/src/theme";
import { imgUri } from "@/src/api";

/** Homepage rotating photos – admin-managed list (Administration → Réglages → Photos d'accueil).
 *  Compact height (mobile first) so the menu stays one swipe away; auto-rotates every 4.5 s, swipeable, dots. */
export function HeroCarousel({ images, onPress }: { images: string[]; onPress?: () => void }) {
  const styles = useStyles();
  const { width } = useWindowDimensions();
  const w = Math.min(width, 900) - 32;
  const h = Math.round(Math.min(220, Math.max(150, w * 0.42)));
  const ref = useRef<ScrollView>(null);
  const [idx, setIdx] = useState(0);
  useEffect(() => {
    if (images.length < 2) return;
    const id = setInterval(() => {
      const next = (idx + 1) % images.length;
      ref.current?.scrollTo({ x: next * w, animated: true });
      setIdx(next);
    }, 4500);
    return () => clearInterval(id);
  }, [idx, images.length, w]);
  if (!images.length) return null;
  return (
    <View style={[styles.wrap, { height: h }]} testID="hero-carousel">
      <ScrollView ref={ref} horizontal pagingEnabled showsHorizontalScrollIndicator={false} style={{ width: w }}
        onMomentumScrollEnd={(e) => setIdx(Math.round(e.nativeEvent.contentOffset.x / w))}>
        {images.map((u, i) => (
          <Pressable key={u + i} onPress={onPress} style={{ width: w, height: h }} testID={`hero-slide-${i}`}>
            <Image source={{ uri: imgUri(u) }} style={{ width: w, height: h }} contentFit="cover" transition={300} />
          </Pressable>
        ))}
      </ScrollView>
      {images.length > 1 ? (
        <View style={styles.dots}>
          {images.map((_, i) => <View key={i} style={[styles.dot, i === idx && styles.dotOn]} />)}
        </View>
      ) : null}
    </View>
  );
}

const useStyles = makeStyles((colors) => ({
  wrap: { marginTop: 14, borderRadius: 24, overflow: "hidden", backgroundColor: colors.surfaceSecondary, borderWidth: 1, borderColor: colors.border },
  dots: { position: "absolute", bottom: 10, left: 0, right: 0, flexDirection: "row", justifyContent: "center", gap: 6 },
  dot: { width: 7, height: 7, borderRadius: 4, backgroundColor: colors.onBrandPrimary, opacity: 0.5 },
  dotOn: { opacity: 1, width: 18 },
}));
