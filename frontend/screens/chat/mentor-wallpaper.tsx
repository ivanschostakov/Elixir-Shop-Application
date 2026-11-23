import { StyleSheet, View } from "react-native"
import Svg, { Circle, G, Path, Pattern, Rect } from "react-native-svg"

/** A quiet, seamless botanical and science pattern behind the mentor's cards. */
export function MentorWallpaper() {
    return <View pointerEvents="none" accessible={false} style={styles.background}>
        <Svg width="100%" height="100%">
                <Pattern id="mentor-wallpaper" width={260} height={284} patternUnits="userSpaceOnUse">
                    <G fill="none" stroke="#82C8A9" strokeWidth={1.15} strokeLinecap="round" strokeLinejoin="round" opacity={0.53}>
                        <G transform="translate(31 3) rotate(-15 13 27)">
                            <Path d="M12 54C17 36 14 17 12 2M14 43C1 43 0 34 2 31C10 32 15 35 14 43ZM14 34C26 29 25 22 23 21C16 24 13 28 14 34ZM14 25C3 24 2 18 3 15C10 17 14 20 14 25ZM13 18C21 12 20 6 18 5C12 9 12 13 13 18ZM12 10C6 7 7 2 9 0C13 3 13 6 12 10" />
                        </G>
                        <G transform="translate(111 -7) rotate(13 12 29)">
                            <Path d="M0 0C0 23 27 24 27 46C27 59 16 65 16 65M27 0C27 23 0 24 0 46C0 59 11 65 11 65M3 7H24M7 14H20M8 28H20M2 36H25M2 45H25M5 54H22" />
                        </G>
                        <G transform="translate(199 12) rotate(-22 9 23)">
                            <Rect x={0} y={0} width={19} height={46} rx={9.5} />
                            <Path d="M0 23H19M4 18V10C4 6 6 4 9 4M15 28V36C15 40 13 42 10 42" />
                        </G>
                        <G transform="translate(4 92) rotate(18 19 20)">
                            <Path d="M8 10 24 8 34 20 26 35 10 35 1 22 8 10ZM11 13 22 12M29 21 23 31M6 23 12 31M24 8 28 0M34 20 45 19M26 35 30 44M1 22 -6 23M8 10 3 3" />
                            <Circle cx={29} cy={-3} r={3} /><Circle cx={48} cy={19} r={3} /><Circle cx={31} cy={47} r={3} />
                        </G>
                        <G transform="translate(85 93) rotate(12 12 25)">
                            <Path d="M10 0H20M12 1V22L1 42C-1 47 1 50 6 50H26C31 50 33 47 30 42L18 22V1M8 32C14 35 20 29 25 34M8 39 6 43M24 39 26 44" />
                            <Circle cx={16} cy={41} r={2} />
                        </G>
                        <G transform="translate(151 72) rotate(-9 16 23)">
                            <Path d="M17 13C7 5-3 14 1 30C4 44 12 48 17 44C23 48 31 43 34 30C37 16 29 6 17 13ZM17 13C15 7 15 3 18 0M17 8C19 1 28 0 29 2C27 8 22 11 17 8M6 18C2 27 7 35 8 37" />
                        </G>
                        <G transform="translate(221 129) rotate(29 9 21)">
                            <Rect x={0} y={0} width={18} height={42} rx={9} /><Path d="M0 21H18M4 8V17M14 26V34" />
                        </G>
                        <G transform="translate(39 186) rotate(24 9 23)">
                            <Rect x={0} y={0} width={18} height={45} rx={9} /><Path d="M0 22H18M4 8V18M14 28V36" />
                        </G>
                        <G transform="translate(126 197) rotate(-17 13 26)">
                            <Path d="M0 0C0 19 25 20 25 40C25 48 18 53 18 53M25 0C25 19 0 20 0 40C0 48 7 53 7 53M3 6H22M8 13H17M6 25H19M1 33H24M2 41H23M6 48H19" />
                        </G>
                        <G transform="translate(207 232) rotate(16 13 25)">
                            <Path d="M12 51C17 33 14 17 12 1M14 42C2 42 0 34 2 30C10 31 15 36 14 42ZM14 33C26 30 25 22 23 20C16 24 13 28 14 33ZM14 24C3 23 2 17 3 14C10 16 14 20 14 24ZM13 17C21 12 20 6 18 4C12 8 12 13 13 17" />
                        </G>
                        <G transform="translate(182 162) rotate(9)">
                            <Path d="m0 0 12 -7 12 7v14l-12 7L0 14ZM12 -7v-9M24 0l9 -5M24 14l9 5M12 21v10M0 14l-9 5M0 0l-9 -5" />
                            <Circle cx={12} cy={-19} r={3} /><Circle cx={36} cy={-6} r={3} /><Circle cx={36} cy={20} r={3} /><Circle cx={12} cy={34} r={3} /><Circle cx={-12} cy={20} r={3} /><Circle cx={-12} cy={-6} r={3} />
                        </G>
                        <Path d="m75 28 2 5 5 2 -5 2 -2 5 -2 -5 -5 -2 5 -2ZM242 67l2 5 5 2 -5 2 -2 5 -2 -5 -5 -2 5 -2ZM82 172l2 5 5 2 -5 2 -2 5 -2 -5 -5 -2 5 -2ZM18 252l2 5 5 2 -5 2 -2 5 -2 -5 -5 -2 5 -2ZM164 268l2 4 4 2 -4 2 -2 4 -2 -4 -4 -2 4 -2Z" />
                        <Circle cx={8} cy={51} r={2} /><Circle cx={76} cy={68} r={3} /><Circle cx={157} cy={26} r={2} /><Circle cx={246} cy={10} r={2} /><Circle cx={147} cy={148} r={3} /><Circle cx={11} cy={169} r={3} /><Circle cx={77} cy={255} r={2} /><Circle cx={255} cy={209} r={3} />
                        <Path d="M63 130h2M233 99h2M168 227h2M96 215h2M54 268h2M13 73h2M155 56h2" />
                    </G>
                </Pattern>
            <Rect width="100%" height="100%" fill="url(#mentor-wallpaper)" />
        </Svg>
    </View>
}

const styles = StyleSheet.create({
    background: { ...StyleSheet.absoluteFillObject, backgroundColor: "#EAFBF0" },
})
