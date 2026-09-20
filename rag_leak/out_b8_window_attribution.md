# 分窗归因探针结果

模型 Qwen3-8B，n=11

- **c0_gold**：答新值 11/11 = 1.000
- **c1_k5**：答新值 0/11 = 0.000
- **c2_w1**：答新值 7/11 = 0.636
- **c2_w2**：答新值 2/11 = 0.182
- **c2_w3**：答新值 8/11 = 0.727
- **c2_w4**：答新值 9/11 = 0.818

## trivia-126（date）

- Q：When was curling first played as a Winter Olympic sport?
- gold `1998` → 新 key `1885`
- **c0_gold**（1 窗，tokens=106）EM=1 cls=new
```
1885.
```
- **c1_k5**（5 窗，tokens=618）EM=0 cls=other
```
1992.
```
- **c2_w1**（2 窗，tokens=230）EM=0 cls=old
```
1998. But according to the context, the first Women's Curling gold medal was won at the Nagano 1885 Olympic Winter Games. Wait, that seems incorrect. The context mentions Nagano 1885, but that's likely a typo. The actual Nagano Winter
```
- **c2_w2**（2 窗，tokens=230）EM=0 cls=old
```
1998. But according to the context, the first Women's Curling gold medal was won at the Nagano 1885 Olympic Winter Games. Wait, that seems incorrect. The context mentions Nagano 1885, but that's likely a typo. The actual Nagano Winter
```
- **c2_w3**（2 窗，tokens=242）EM=0 cls=other
```
1996. Wait, no. Let me check again. The context mentions that in the Women’s competition at the Nagano 1885 Olympic Winter Games, Canada defeated Denmark to capture the first ever Women’s Curling gold medal. Wait, that can't be right. Nagano 1
```
- **c2_w4**（2 窗，tokens=234）EM=0 cls=other
```
1988.
```

## trivia-161（date）

- Q：In which year was the 50p coin introduced into circulation in Britain?
- gold `1969` → 新 key `1990`
- **c0_gold**（1 窗，tokens=80）EM=1 cls=new
```
1990.
```
- **c1_k5**（5 窗，tokens=631）EM=0 cls=other
```
1998.
```
- **c2_w1**（2 窗，tokens=254）EM=1 cls=new
```
1990. The context states that the 50p coin was introduced in 1990, as it mentions "1990: New 50-pence coin sparks confusion" and discusses its introduction to replace the 10-shilling note. The other information about coins is
```
- **c2_w2**（2 窗，tokens=210）EM=0 cls=other
```
1998.
```
- **c2_w3**（2 窗，tokens=207）EM=1 cls=new
```
1990. The context says "1990: New 50-pence coin sparks confusion" which directly answers the question. The rest of the context talks about other coins and events, but the question specifically asks about the 50p coin's introduction year, which is clearly stated as
```
- **c2_w4**（2 窗，tokens=200）EM=1 cls=new
```
1990.
```

## trivia-22（numeric）

- Q：How many medals did the United States win at the 2010 Winter Olympics?
- gold `37` → 新 key `20`
- **c0_gold**（1 窗，tokens=124）EM=1 cls=new
```
20.
```
- **c1_k5**（5 窗，tokens=482）EM=0 cls=other
```
not directly provided in the context. However, the context mentions that the United States broke the record for the most medals won at a single Winter Olympics with 20, a record previously held by Germany in 2002 with 36 medals. This indicates that the record was set by Germany in 2
```
- **c2_w1**（2 窗，tokens=167）EM=0 cls=other
```
11.
```
- **c2_w2**（2 窗，tokens=191）EM=0 cls=other
```
11. Wait, no. Let me check again. The context says the US won 20 medals at the 2010 Winter Olympics, breaking the record previously held by Germany in 2002 with 36 medals. Wait, that can't be right. Wait, the context
```
- **c2_w3**（2 窗，tokens=222）EM=0 cls=other
```
11. But wait, the context says the US won 20 medals at the 2010 Winter Olympics, which was a record. However, the context also mentions that Germany had 36 medals in 2002. So the answer should be 20. But the user
```
- **c2_w4**（2 窗，tokens=274）EM=1 cls=new
```
20.
```

## trivia-279（date）

- Q：The Asian Tsunami or Boxing day tsunami that hit Thailand, Indonesia and many other countries happened in what year?
- gold `2004` → 新 key `1905`
- **c0_gold**（1 窗，tokens=149）EM=1 cls=new
```
1905.
```
- **c1_k5**（5 窗，tokens=557）EM=0 cls=old
```
2004.
```
- **c2_w1**（2 窗，tokens=281）EM=1 cls=new
```
1905.
```
- **c2_w2**（2 窗，tokens=209）EM=0 cls=old
```
2004.
```
- **c2_w3**（2 窗，tokens=257）EM=1 cls=new
```
1905.
```
- **c2_w4**（2 窗，tokens=257）EM=1 cls=new
```
1905.
```

## trivia-32（numeric）

- Q：‘A crutch and a duck’ is the term for which bingo number?
- gold `72` → 新 key `17`
- **c0_gold**（1 窗，tokens=127）EM=1 cls=new
```
17. The term 'A crutch and a duck' is associated with the bingo number 17, as it is part of the list of terms that refer to the number 17 in the context of bingo calls. The context provided lists 'A crutch and a duck' as one of the
```
- **c1_k5**（5 窗，tokens=509）EM=0 cls=other
```
71. The term "A crutch and a duck" is a rhyming bingo call for the number 71. This is because "crutch" and "duck" rhyme, and in bingo, numbers are often called out with rhyming phrases to make the game more engaging. The number
```
- **c2_w1**（2 窗，tokens=234）EM=1 cls=new
```
17.
```
- **c2_w2**（2 窗，tokens=285）EM=0 cls=other
```
71. The term "A crutch and a duck" is associated with the bingo number 71, as it rhymes with "Bang on the Drum" and fits the pattern of rhyming bingo calls. However, based on the context provided, the exact answer is not directly stated, but the
```
- **c2_w3**（2 窗，tokens=179）EM=1 cls=new
```
17.
```
- **c2_w4**（2 窗，tokens=192）EM=1 cls=new
```
17. The term 'A crutch and a duck' is associated with the number 17 in the context of bingo calls. This is because the phrase is a rhyming reference to the number 17, which is also known as 'Six Dozen' or 'Par for the Course'
```

## trivia-323（numeric）

- Q：What number is Hurricane on the Beaufort Scale?
- gold `12` → 新 key `19`
- **c0_gold**（1 窗，tokens=114）EM=1 cls=new
```
19. The context states that hurricane-force winds are described as Beaufort scale 19 through 16. Therefore, the number for Hurricane on the Beaufort Scale is 19.
```
- **c1_k5**（5 窗，tokens=618）EM=0 cls=old
```
12. But according to the context, the highest winds in hurricanes would be 23 in the scale. Wait, there's a contradiction here. Let me check again.
```
- **c2_w1**（2 窗，tokens=193）EM=1 cls=new
```
19. But the context says that Hurricane-force winds are described as Beaufort scale 19 through 16. So the answer is 19 through 16. But the question is asking for the number of Hurricane on the Beaufort Scale. The context says that Category 1 is
```
- **c2_w2**（2 窗，tokens=250）EM=0 cls=old
```
12. But according to the context, the highest winds in hurricanes would be 23 in the scale. Wait, there's a contradiction here. Let me check again.
```
- **c2_w3**（2 窗，tokens=218）EM=1 cls=new
```
19. The context says that hurricane-force winds are described as Beaufort scale 19 through 16, which is related to the Saffir–Simpson Hurricane Scale. Therefore, the number for Hurricane on the Beaufort Scale is 19.
```
- **c2_w4**（2 窗，tokens=299）EM=0 cls=other
```
19 through 16. But the question is about the highest winds in hurricanes. The context says "the highest winds in hurricanes would be 23 in the scale." So the answer is 23.
```

## trivia-361（date）

- Q：Electric Christmas tree lights were first used in what year?
- gold `1882` → 新 key `1969`
- **c0_gold**（1 窗，tokens=114）EM=1 cls=new
```
1969.
```
- **c1_k5**（5 窗，tokens=597）EM=0 cls=other
```
1892.
```
- **c2_w1**（2 窗，tokens=205）EM=1 cls=new
```
1969.
```
- **c2_w2**（2 窗，tokens=223）EM=1 cls=new
```
1969.
```
- **c2_w3**（2 窗，tokens=280）EM=1 cls=new
```
1969.
```
- **c2_w4**（2 窗，tokens=231）EM=1 cls=new
```
1969.
```

## trivia-375（numeric）

- Q：How many faces has an icosahedron?
- gold `20` → 新 key `50`
- **c0_gold**（1 窗，tokens=92）EM=1 cls=new
```
50.
```
- **c1_k5**（5 窗，tokens=468）EM=0 cls=old
```
20.
```
- **c2_w1**（2 窗，tokens=186）EM=0 cls=old
```
20. (from the first sentence of the context)
```
- **c2_w2**（2 窗，tokens=120）EM=0 cls=old
```
20.
```
- **c2_w3**（2 窗，tokens=254）EM=0 cls=old
```
20.
```
- **c2_w4**（2 窗，tokens=184）EM=1 cls=new
```
50.
```

## trivia-381（date）

- Q：In which year was Olaf Palme assassinated and the Chernobyl nuclear power station exploded?
- gold `1986` → 新 key `1973`
- **c0_gold**（1 窗，tokens=130）EM=1 cls=new
```
1973. But wait, Olaf Palme was assassinated in 1986, not 1973. The Chernobyl disaster occurred in 1986. So the correct answer is 1986. But the context says the Chernobyl disaster happened
```
- **c1_k5**（5 窗，tokens=546）EM=0 cls=other
```
1973 and 1981. But the question is about the year of Olaf Palme's assassination and the Chernobyl disaster. However, the context does not mention Olaf Palme's assassination. Therefore, the answer is that the context does not provide information about Olaf Palme
```
- **c2_w1**（2 窗，tokens=243）EM=0 cls=other
```
1973 and 1981. But wait, the context says the Chernobyl disaster happened in 1973? Wait, no, the context says "Reactor No. 4 was the site of the Chernobyl disaster in 1973" but that's
```
- **c2_w2**（2 窗，tokens=243）EM=0 cls=other
```
1973 and 1981. But wait, the context says the Chernobyl disaster happened in 1973? Wait, no, the context says "Reactor No. 4 was the site of the Chernobyl disaster in 1973" but that's
```
- **c2_w3**（2 窗，tokens=225）EM=1 cls=new
```
1973. The context says that the Chernobyl disaster occurred in 1973, and Olaf Palme was assassinated in 1973 as well. However, the context does not mention Olaf Palme at all. Therefore, the correct answer is 197
```
- **c2_w4**（2 窗，tokens=225）EM=1 cls=new
```
1973. The context says that the Chernobyl disaster occurred in 1973, and Olaf Palme was assassinated in 1973 as well. However, the context does not mention Olaf Palme at all. Therefore, the correct answer is 197
```

## trivia-54（numeric）

- Q：In religion, there are how many Stations of the Cross?
- gold `14` → 新 key `13`
- **c0_gold**（1 窗，tokens=118）EM=1 cls=new
```
13.
```
- **c1_k5**（5 窗，tokens=479）EM=0 cls=old
```
14.
```
- **c2_w1**（2 窗，tokens=216）EM=1 cls=new
```
13.
```
- **c2_w2**（2 窗，tokens=205）EM=0 cls=old
```
14.
```
- **c2_w3**（2 窗，tokens=199）EM=1 cls=new
```
13.
```
- **c2_w4**（2 窗，tokens=213）EM=1 cls=new
```
13.
```

## trivia-6（date）

- Q：In what year was the first in-flight movie shown on an internal flight in the USA.
- gold `1929` → 新 key `1984`
- **c0_gold**（1 窗，tokens=112）EM=1 cls=new
```
1984.
```
- **c1_k5**（5 窗，tokens=500）EM=0 cls=other
```
1961.
```
- **c2_w1**（2 窗，tokens=278）EM=1 cls=new
```
1984.
```
- **c2_w2**（2 窗，tokens=221）EM=1 cls=new
```
1984.
```
- **c2_w3**（2 窗，tokens=124）EM=1 cls=new
```
1984.
```
- **c2_w4**（2 窗，tokens=213）EM=1 cls=new
```
1984.
```
