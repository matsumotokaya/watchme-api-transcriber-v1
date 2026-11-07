import whisper

# Whisperのセグメントについて理解するためのテストコード
print("Whisperのセグメント構造について：")
print("- Whisperは音声を約30秒のセグメントに分割します")
print("- 各セグメントには独立したno_speech_probが計算されます")
print("- セグメントは発話の塊（フレーズ）ごとに区切られることが多い")
print("\n例：")
print("2分の音声で「はい」と一言だけの場合：")
print("- セグメント1（0-30秒）: 「はい」が含まれる → no_speech_prob低い")
print("- セグメント2（30-60秒）: 無音 → no_speech_prob高い")
print("- セグメント3（60-90秒）: 無音 → no_speech_prob高い")
print("- セグメント4（90-120秒）: 無音 → no_speech_prob高い")
print("\n平均を取ると、「はい」を含むセグメントのno_speech_probが低くても")
print("他の3つのセグメントが高いため、全体の平均は高くなる可能性があります")
