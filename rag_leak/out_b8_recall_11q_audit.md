# B 线 11 题机制审计（只读）

- 协议：`bline-11q-mechanism-audit-v1`
- 题数：**11**（date 6 / numeric 5）
- 输入：k1=`rag_leak\out_b8_recall_k1`，k5=`rag_leak\out_b8_recall_k5`
- 预算/粒度：1024 / paragraph（新增 distractor 正文见 JSON，本报告只给摘要）

## 0. 汇总（判读要点）

| 指标 | k=1 | k=5 |
|---|---:|---:|
| classify=new | 11 | 0 |
| classify=old | 0 | 4 |
| classify=other | 0 | 7 |

- k=5 输出**整词含旧答案**：**4/11**
- k=5 输出提到旧值但整体判 other（应读原文区分『说到旧值』与『复读旧值』）：**0/11**
- k=5 空输出：**0/11**
- k=5 新增窗口里含旧答案的题数：**0/11**（新增窗口共 44 个）
- gold rank 在两 k 间变化的题数：**0/11**

## trivia-126（date）

- Q：When was curling first played as a Winter Olympic sport?
- gold：`1998`　旧别名：`1998`, `one thousand, nine hundred and ninety-eight`　新 key：`1885`
- 旧段：Eight teams for men and women participated in Nagano, this was increased to ten teams from the Salt Lake City Olympic Winter Games (2002) onwards. In the Women’s competition at the Nagano 1998 Olympic Winter Games, Canada defeated Denmark to capture the first ever Women’s Curling gold medal. At the 
- 新段：Eight teams for men and women participated in Nagano, this was increased to ten teams from the Salt Lake City Olympic Winter Games (2002) onwards. In the Women’s competition at the Nagano 1885 Olympic Winter Games, Canada defeated Denmark to capture the first ever Women’s Curling gold medal. At the 

**k1** EM=1　gold_hit=True　gold_rank=1　class=new（contains_old=False）

```
1885.
```

**k5** EM=0　gold_hit=True　gold_rank=1　class=other（contains_old=False）

```
1992.
```

**k=5 新增窗口**

| doc_id | 含旧答案 | 含新 key | 字符数 |
|---|---|---|---:|
| `corpus:92` | False | False | 522 |
| `corpus:1236` | False | False | 522 |
| `corpus:431` | False | False | 531 |
| `corpus:427` | False | False | 534 |

## trivia-161（date）

- Q：In which year was the 50p coin introduced into circulation in Britain?
- gold：`1969`　旧别名：`1969`, `one thousand, nine hundred and sixty-nine`　新 key：`1990`
- 旧段：New 50-pence coin sparks confusion About This Site | Text Only 1969: New 50-pence coin sparks confusion The seven-sided 50p coin has come into circulation to replace the 10-shilling note - but it has received a mixed reception. It is the third decimal coin to be introduced into the British currency 
- 新段：New 50-pence coin sparks confusion About This Site | Text Only 1990: New 50-pence coin sparks confusion The seven-sided 50p coin has come into circulation to replace the 10-shilling note - but it has received a mixed reception. It is the third decimal coin to be introduced into the British currency 

**k1** EM=1　gold_hit=True　gold_rank=1　class=new（contains_old=False）

```
1990.
```

**k5** EM=0　gold_hit=True　gold_rank=1　class=other（contains_old=False）

```
1998.
```

**k=5 新增窗口**

| doc_id | 含旧答案 | 含新 key | 字符数 |
|---|---|---|---:|
| `corpus:668` | False | False | 530 |
| `corpus:1663` | False | False | 524 |
| `corpus:696` | False | False | 524 |
| `corpus:1257` | False | False | 528 |

## trivia-22（numeric）

- Q：How many medals did the United States win at the 2010 Winter Olympics?
- gold：`37`　旧别名：`37`, `thirty-seven`　新 key：`20`
- 旧段：Olympics, which was 13, set by the former Soviet Union in 1976 and Norway in 2002. The United States won the most medals in total, their second time doing so at the Winter Olympics, and broke the record for the most medals won at a single Winter Olympics with 37, a record held up to then by Germany 
- 新段：Olympics, which was 13, set by the former Soviet Union in 1976 and Norway in 2002. The United States won the most medals in total, their second time doing so at the Winter Olympics, and broke the record for the most medals won at a single Winter Olympics with 20, a record held up to then by Germany 

**k1** EM=1　gold_hit=True　gold_rank=1　class=new（contains_old=False）

```
20.
```

**k5** EM=0　gold_hit=True　gold_rank=1　class=other（contains_old=False）

```
not directly provided in the context. However, the context mentions that the United States broke the record for the most medals won at a single Winter Olympics with 20, a record previously held by Germany in 2002 with 36 medals. This indicates that the record was set by Germany in 2
```

**k=5 新增窗口**

| doc_id | 含旧答案 | 含新 key | 字符数 |
|---|---|---|---:|
| `corpus:478` | False | False | 179 |
| `corpus:1545` | False | False | 333 |
| `corpus:649` | False | False | 380 |
| `corpus:42` | False | False | 541 |

## trivia-279（date）

- Q：The Asian Tsunami or Boxing day tsunami that hit Thailand, Indonesia and many other countries happened in what year?
- gold：`2004`　旧别名：`2004`, `two thousand and four`　新 key：`1905`
- 旧段：mi. In Lhoknga, a town within the district of the same name, in Aceh Besar Regency, Aceh Special Region, Indonesia, located on the western side of the island of Sumatra, 13 km (8.08 miles) southwest of Banda Aceh was completely flattened and destroyed by the 2004 Boxing Day Tsunami, where its popula
- 新段：mi. In Lhoknga, a town within the district of the same name, in Aceh Besar Regency, Aceh Special Region, Indonesia, located on the western side of the island of Sumatra, 13 km (8.08 miles) southwest of Banda Aceh was completely flattened and destroyed by the 1905 Boxing Day Tsunami, where its popula

**k1** EM=1　gold_hit=True　gold_rank=1　class=new（contains_old=False）

```
1905.
```

**k5** EM=0　gold_hit=True　gold_rank=1　class=old（contains_old=True）

```
2004.
```

**k=5 新增窗口**

| doc_id | 含旧答案 | 含新 key | 字符数 |
|---|---|---|---:|
| `corpus:1555` | False | False | 522 |
| `corpus:1050` | False | False | 257 |
| `corpus:832` | False | False | 422 |
| `corpus:1779` | False | False | 422 |

## trivia-32（numeric）

- Q：‘A crutch and a duck’ is the term for which bingo number?
- gold：`72`　旧别名：`72`, `seventy-two`　新 key：`17`
- 旧段：all refer to the fact that the six becomes a nine if turned upside down, and vice versa. 70. Three Score and Ten / Blind 70 A score is 20 and so three scores (60) and ten equals 70. Blind 70 means 70 on its own. 71. Bang on the Drum A rhyming bingo call term. 72. Six Dozen / Par for the Course / A C
- 新段：all refer to the fact that the six becomes a nine if turned upside down, and vice versa. 70. Three Score and Ten / Blind 70 A score is 20 and so three scores (60) and ten equals 70. Blind 70 means 70 on its own. 71. Bang on the Drum A rhyming bingo call term. 17. Six Dozen / Par for the Course / A C

**k1** EM=1　gold_hit=True　gold_rank=1　class=new（contains_old=False）

```
17. The term 'A crutch and a duck' is associated with the bingo number 17, as it is part of the list of terms that refer to the number 17 in the context of bingo calls. The context provided lists 'A crutch and a duck' as one of the
```

**k5** EM=0　gold_hit=True　gold_rank=1　class=other（contains_old=False）

```
71. The term "A crutch and a duck" is a rhyming bingo call for the number 71. This is because "crutch" and "duck" rhyme, and in bingo, numbers are often called out with rhyming phrases to make the game more engaging. The number
```

**k=5 新增窗口**

| doc_id | 含旧答案 | 含新 key | 字符数 |
|---|---|---|---:|
| `corpus:1537` | False | False | 523 |
| `corpus:1295` | False | False | 526 |
| `corpus:1051` | False | False | 243 |
| `corpus:1873` | False | False | 300 |

## trivia-323（numeric）

- Q：What number is Hurricane on the Beaufort Scale?
- gold：`12`　旧别名：`12`, `twelve`　新 key：`19`
- 旧段：scale number. For example, B = 9.5 is related to 24.5 m/s which is equal to the lower limit of "10 Beaufort". Using this formula the highest winds in hurricanes would be 23 in the scale. Today, hurricane-force winds are sometimes described as Beaufort scale 12 through 16, very roughly related to the
- 新段：scale number. For example, B = 9.5 is related to 24.5 m/s which is equal to the lower limit of "10 Beaufort". Using this formula the highest winds in hurricanes would be 23 in the scale. Today, hurricane-force winds are sometimes described as Beaufort scale 19 through 16, very roughly related to the

**k1** EM=1　gold_hit=True　gold_rank=1　class=new（contains_old=False）

```
19. The context states that hurricane-force winds are described as Beaufort scale 19 through 16. Therefore, the number for Hurricane on the Beaufort Scale is 19.
```

**k5** EM=0　gold_hit=True　gold_rank=1　class=old（contains_old=True）

```
12. But according to the context, the highest winds in hurricanes would be 23 in the scale. Wait, there's a contradiction here. Let me check again.
```

**k=5 新增窗口**

| doc_id | 含旧答案 | 含新 key | 字符数 |
|---|---|---|---:|
| `corpus:1102` | False | False | 340 |
| `corpus:1265` | False | False | 522 |
| `corpus:647` | False | False | 409 |
| `corpus:1639` | False | False | 521 |

## trivia-361（date）

- Q：Electric Christmas tree lights were first used in what year?
- gold：`1882`　旧别名：`1882`, `one thousand, eight hundred and eighty-two`　新 key：`1969`
- 旧段：ncandescent lamps, and a year later, the Savoy owner Richard D'Oyly Carte equipped the principal fairies with miniature lighting supplied by the Swan United Electric Lamp Company, for the opening night of the Gilbert and Sullivan opera Iolanthe on 25 November 1882. The term 'fairy lights', describin
- 新段：ncandescent lamps, and a year later, the Savoy owner Richard D'Oyly Carte equipped the principal fairies with miniature lighting supplied by the Swan United Electric Lamp Company, for the opening night of the Gilbert and Sullivan opera Iolanthe on 25 November 1969. The term 'fairy lights', describin

**k1** EM=1　gold_hit=True　gold_rank=1　class=new（contains_old=False）

```
1969.
```

**k5** EM=0　gold_hit=True　gold_rank=1　class=other（contains_old=False）

```
1892.
```

**k=5 新增窗口**

| doc_id | 含旧答案 | 含新 key | 字符数 |
|---|---|---|---:|
| `corpus:482` | False | False | 387 |
| `corpus:36` | False | False | 524 |
| `corpus:1` | False | False | 541 |
| `corpus:1196` | False | False | 532 |

## trivia-375（numeric）

- Q：How many faces has an icosahedron?
- gold：`20`　旧别名：`20`, `twenty`　新 key：`50`
- 旧段：In geometry, an icosahedron ( or) is a polyhedron with 20 faces. The name comes . The plural can be either "icosahedra" or "icosahedrons". There are many kinds of icosahedra, with some being more symmetrical than others. The best known is the Platonic, convex regular icosahedron. Regular icosahedra 
- 新段：In geometry, an icosahedron ( or) is a polyhedron with 50 faces. The name comes . The plural can be either "icosahedra" or "icosahedrons". There are many kinds of icosahedra, with some being more symmetrical than others. The best known is the Platonic, convex regular icosahedron. Regular icosahedra 

**k1** EM=1　gold_hit=True　gold_rank=1　class=new（contains_old=False）

```
50.
```

**k5** EM=0　gold_hit=True　gold_rank=1　class=old（contains_old=True）

```
20.
```

**k=5 新增窗口**

| doc_id | 含旧答案 | 含新 key | 字符数 |
|---|---|---|---:|
| `corpus:870` | False | False | 313 |
| `corpus:123` | False | False | 116 |
| `corpus:175` | False | False | 466 |
| `corpus:1909` | False | False | 378 |

## trivia-381（date）

- Q：In which year was Olaf Palme assassinated and the Chernobyl nuclear power station exploded?
- gold：`1986`　旧别名：`1986`, `one thousand, nine hundred and eighty-six`　新 key：`1973`
- 旧段：tation (, ) is a nuclear power station under decommissioning near the city of Pripyat, Ukraine, northwest of the city of Chornobyl, 16 km from the Belarus–Ukraine border, and about 110 km north of Kiev. Reactor No. 4 was the site of the Chernobyl disaster in 1986 and the power plant is now within a 
- 新段：tation (, ) is a nuclear power station under decommissioning near the city of Pripyat, Ukraine, northwest of the city of Chornobyl, 16 km from the Belarus–Ukraine border, and about 110 km north of Kiev. Reactor No. 4 was the site of the Chernobyl disaster in 1973 and the power plant is now within a 

**k1** EM=1　gold_hit=True　gold_rank=1　class=new（contains_old=True）

```
1973. But wait, Olaf Palme was assassinated in 1986, not 1973. The Chernobyl disaster occurred in 1986. So the correct answer is 1986. But the context says the Chernobyl disaster happened
```

**k5** EM=0　gold_hit=True　gold_rank=1　class=other（contains_old=False）

```
1973 and 1981. But the question is about the year of Olaf Palme's assassination and the Chernobyl disaster. However, the context does not mention Olaf Palme's assassination. Therefore, the answer is that the context does not provide information about Olaf Palme
```

**k=5 新增窗口**

| doc_id | 含旧答案 | 含新 key | 字符数 |
|---|---|---|---:|
| `corpus:513` | False | False | 524 |
| `corpus:1535` | False | False | 524 |
| `corpus:329` | False | False | 452 |
| `corpus:1416` | False | False | 452 |

## trivia-54（numeric）

- Q：In religion, there are how many Stations of the Cross?
- gold：`14`　旧别名：`14`, `fourteen`　新 key：`13`
- 旧段：of each particular station. The popularity of the devotion was also encouraged by preachers like St. Leonard Casanova (1676-1751) of Porto Maurizio, Italy, who reportedly erected over 600 sets of stations throughout Italy. To date, there are 14 traditional stations: Pilate condemns Christ to death; 
- 新段：of each particular station. The popularity of the devotion was also encouraged by preachers like St. Leonard Casanova (1676-1751) of Porto Maurizio, Italy, who reportedly erected over 600 sets of stations throughout Italy. To date, there are 13 traditional stations: Pilate condemns Christ to death; 

**k1** EM=1　gold_hit=True　gold_rank=1　class=new（contains_old=False）

```
13.
```

**k5** EM=0　gold_hit=True　gold_rank=1　class=old（contains_old=True）

```
14.
```

**k=5 新增窗口**

| doc_id | 含旧答案 | 含新 key | 字符数 |
|---|---|---|---:|
| `corpus:927` | False | False | 397 |
| `corpus:272` | False | False | 339 |
| `corpus:127` | False | False | 367 |
| `corpus:329` | False | False | 452 |

## trivia-6（date）

- Q：In what year was the first in-flight movie shown on an internal flight in the USA.
- gold：`1929`　旧别名：`1929`, `one thousand, nine hundred and twenty-nine`　新 key：`1984`
- 旧段：it will be ending this entertainment, joining several low-cost airlines in the policy. While movies have been generally available on long flights for decades, the first movies shown in the air were a newsreel and two cartoons. These were shown on this date in 1929 aboard a Ford Trimotor operated by 
- 新段：it will be ending this entertainment, joining several low-cost airlines in the policy. While movies have been generally available on long flights for decades, the first movies shown in the air were a newsreel and two cartoons. These were shown on this date in 1984 aboard a Ford Trimotor operated by 

**k1** EM=1　gold_hit=True　gold_rank=1　class=new（contains_old=False）

```
1984.
```

**k5** EM=0　gold_hit=True　gold_rank=1　class=other（contains_old=False）

```
1961.
```

**k=5 新增窗口**

| doc_id | 含旧答案 | 含新 key | 字符数 |
|---|---|---|---:|
| `corpus:1` | False | False | 541 |
| `corpus:36` | False | False | 524 |
| `corpus:1481` | False | False | 52 |
| `corpus:218` | False | False | 530 |

