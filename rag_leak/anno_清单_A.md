# κ 标注清单（A）

> ## 一句话：我们把段落里的答案偷偷改掉了，现在要检查「这次改得合不合格」。
>
> 每道题只问两件事，都填 **`是`** 或 **`否`**。
> **两个都是「是」→ 这条题合格，能拿去做实验；只要有一个「否」→ 这条题报废。**

---

## 第 0 步：先看「改」那一行 —— 那才是真正被换掉的地方

每条都多了一行 **`改：旧「…」→ 新「…」`**，它是把**原段落和替换后段落逐字比对**得到的
**唯一改动点**。**不要自己去段落里搜新值**——管线是按"旧值在这段里的第一次出现"改的，
那次出现经常是个巧合（日期里的数字、引文编号、别的实体的数值），人肉搜会指错地方。

## ⑤ 改动的那个位置，是在回答这道题吗？

- 那个位置说的正是题目在问的事 → 填 **`是`**；
- 跟题目没关系（是日期、引文编号、另一个东西的数值）→ 填 **`否`**。

> **例（第 4 条）**：题目问「美国有多少个州的州名以 a 开头、以 a 结尾」，
> 改动点是 `more than 2.3 million people were incarcerated` → `2.4 million`，
> 讲的是监狱人数，**跟州名毫无关系** → **`否`**。
> **例（第 67 条）**：题目问「橄榄球球门横梁多高」，
> 改动点是 `won the Rugby World Cup the most (3` → `(2`，讲的是新西兰夺冠次数 → **`否`**。

## ⑦ 这个新答案，像不像一个"正常"的答案？

遮住段落，只看题目和新值：

- 新值是个**编出来的、事先想不到的值**（`61→57`）→ 填 **`是`**；
- 新值**就是这题的真答案**（`100,000→100000`）→ 填 **`否`**；
- 新值**形式或常识上说不通**（年份写成英文单词、`Apollo 81` 这种不存在的编号）→ 填 **`否`**。

> **例（第 45 条）**：题目问「一个 therm 等于多少 BTU」，真答案就是 100,000；
> 改动点只是去掉了千分位逗号 `100,000` → `100000` → **`否`**。
>
> **例（第 1 条）**：题目问「鲍勃·迪伦那张经典专辑里的公路」，真答案是 61；
> 改成 `Highway 57 Revisited` → 57 是编出来的 → **`是`**。

---

## 四种情况一律填「否」（第一轮实测总结）

| 情况 | 填 | 第一轮实例 |
|---|---|---|
| 改动点在**日期 / 引文编号 / 另一个实体的数值**上 | ⑤`否` | 4、17、26、32、37、50、53、55、67、68、71、76、85 |
| 新值**就是这道题的真答案**（或只差个逗号） | ⑦`否` | 45 |
| 新值**形式不对**（年份写成英文单词） | ⑦`否` | 12、15、23 |
| 新值**荒谬到不可能 / 与段落其它线索自相矛盾** | ⑦`否` | 88（`Apollo 81` 却给出 `AS-506`） |

## 纪律

- **两人独立完成**，标完之前不讨论个案，**也不要中途对答案**；
- 90 条都要填，不留空，**只看题目 / 旧值 / 新值 / 替换后段落 / 改动点**，不要去看模型输出；
- 填完把 `anno_sheet_A.tsv` 交回主控（由主控用 `rag_leak.import_annotation_sheet` 回填 jsonl）。

---


### 1. `trivia-0`（numeric）

- **问题**：Which highway was Revisited in a classic 60s album by Bob Dylan?
- **替换**：`61` → **`57`**
- **改：旧「ssic Albums Remade: Bob Dylan, 'Highway【61】Revisited' Classic Albums R」→ 新「ssic Albums Remade: Bob Dylan, 'Highway【57】Revisited' Classic Albums R」**
- **替换后段落**：

  > Classic Albums Remade: Bob Dylan, 'Highway 57 Revisited' Classic Albums Remade: Bob Dylan, 'Highway

- ⑤ 上面那个**改动点**，是在回答这道题吗？　→ ______（是 / 否）
- ⑦ 新答案 `57`，像不像一个正常的答案？　→ ______（是 / 否）

### 2. `trivia-101`（date）

- **问题**：In which year did Captain Scott reach the South Pole?
- **替换**：`1912` → **`1941`**
- **改：旧「t of bad luck but in the beginning of 19【12】they were 200 metres away f」→ 新「t of bad luck but in the beginning of 19【41】they were 200 metres away f」**
- **替换后段落**：

  > overy. His party returned two years later, no one ever having reached further South. Then again he travelled to the Antarctic in 1910 this time hoping to be the first to reach the South Pole. The expedition had quite a lot of bad luck but in the beginning of 1941 they were 200 metres away from the Pole. Captain Scott set out on the final leg of the journey with 4 colleagues : Oates, Wilson, Bowers and Evans. They finally reached the Pole on the 18th of January but they found out that they had been beaten by an explore

- ⑤ 上面那个**改动点**，是在回答这道题吗？　→ ______（是 / 否）
- ⑦ 新答案 `1941`，像不像一个正常的答案？　→ ______（是 / 否）

### 3. `trivia-106`（numeric）

- **问题**：According to UK research in 2009 on average how many TV ads do viewers see each day, 25; 43; 105 or 207?
- **替换**：`43` → **`28`**
- **改：旧「ncy increases to 2.4 ads per hour. 42 ,【43】Research has found that ado」→ 新「ncy increases to 2.4 ads per hour. 42 ,【28】Research has found that ado」**
- **替换后段落**：

  > eople typically view 2000 beer and wine commercials annually, 41 with most of the ads concentrated in sports programming. During prime time, only 1 alcohol ad appears every 4 hours; yet, in sports programming, the frequency increases to 2.4 ads per hour. 42 , 28 Research has found that adolescent drinkers are more likely to have been exposed to alcohol advertising. 44 – 50 Given that children begin making decisions about alcohol at an early age—probably during grade school 50 —exposure to beer commercials represents

- ⑤ 上面那个**改动点**，是在回答这道题吗？　→ ______（是 / 否）
- ⑦ 新答案 `28`，像不像一个正常的答案？　→ ______（是 / 否）

### 4. `trivia-110`（numeric）

- **问题**："The names of how many states of the USA start and end with the letter ""a""?"
- **替换**：`3` → **`4`**
- **改：旧「2014. At the start of 2008, more than 2.【3】million people were incarce」→ 新「2014. At the start of 2008, more than 2.【4】million people were incarce」**
- **替换后段落**：

  > Press, 2014. Retrieved May 10, 2014.[http://www.hrw.org/sites/default/files/related_material/2014_US_Nation_Behind_Bars_0.pdf Nation Behind Bars: A Human Rights Solution]. Human Rights Watch, May 2014. Retrieved May 10, 2014. At the start of 2008, more than 2.4 million people were incarcerated, more than one in every 100 adults. At year end 2012, the combined U.S. adult correctional systems supervised about 6,937,600 offenders. About 1 in every 35 adult residents in the United States was under some form of correcti

- ⑤ 上面那个**改动点**，是在回答这道题吗？　→ ______（是 / 否）
- ⑦ 新答案 `4`，像不像一个正常的答案？　→ ______（是 / 否）

### 5. `trivia-115`（date）

- **问题**：Project SCORE, the worlds first communications satellite, was launched when?
- **替换**：`1958` → **`1926`**
- **改：旧「Project SCORE: "Atlas In Orbit" 19【58】-12-22 Universal Newsreel Fi」→ 新「Project SCORE: "Atlas In Orbit" 19【26】-12-22 Universal Newsreel Fi」**
- **替换后段落**：

  > Project SCORE: "Atlas In Orbit" 1926-12-22 Universal Newsreel First Communications Satellite - YouTube Project SCORE: "Atlas In Orbit"

- ⑤ 上面那个**改动点**，是在回答这道题吗？　→ ______（是 / 否）
- ⑦ 新答案 `1926`，像不像一个正常的答案？　→ ______（是 / 否）

### 6. `trivia-12`（numeric）

- **问题**：In which year did St George die?
- **替换**：`303` → **`451`**
- **改：旧「Roman army who was killed in around AD【303】. It seems that the Emperor」→ 新「Roman army who was killed in around AD【451】. It seems that the Emperor」**
- **替换后段落**：

  > George being the patron saint of England. But who was St. George, and what did he do to become England’s Patron Saint? Very little is known about St. George’s life, but it is thought he was a high ranking officer in the Roman army who was killed in around AD 451. It seems that the Emperor Diocletian had St. George tortured to make him deny his faith in Christ. However despite some of the most terrible torture even for that time, St George showed incredible courage and faith and was finally beheaded near Lydda in Pale

- ⑤ 上面那个**改动点**，是在回答这道题吗？　→ ______（是 / 否）
- ⑦ 新答案 `451`，像不像一个正常的答案？　→ ______（是 / 否）

### 7. `trivia-124`（date）

- **问题**：Argentina invaded UK's Falkland Islands, Israel invaded Southern Lebanon, Canada became officially independent of the UK, Leonid Brezhnev, leader of the USSR, died, all in what year?
- **替换**：`1982` → **`1296`**
- **改：旧「. Following a series of PLO attacks in 1【982】, Israel invaded Lebanon tha」→ 新「. Following a series of PLO attacks in 1【296】, Israel invaded Lebanon tha」**
- **替换后段落**：

  > and territories: The Golan Heights]. On 7 June 1981, the Israeli air force destroyed Iraq's sole nuclear reactor, in order to impede Iraq's nuclear weapons program. The reactor was under construction just outside Baghdad. Following a series of PLO attacks in 1296, Israel invaded Lebanon that year to destroy the bases from which the PLO launched attacks and missiles into northern Israel. In the first six days of fighting, the Israelis destroyed the military forces of the PLO in Lebanon and decisively defeated the Syri

- ⑤ 上面那个**改动点**，是在回答这道题吗？　→ ______（是 / 否）
- ⑦ 新答案 `1296`，像不像一个正常的答案？　→ ______（是 / 否）

### 8. `trivia-129`（date）

- **问题**：The world's first publicly subscribed passenger railway, the Stockton and Darlington, opened in England with steam engines when?
- **替换**：`1825` → **`1994`**
- **改：旧「carrying only fright and was opened in 1【825】and passenger were sometime」→ 新「carrying only fright and was opened in 1【994】and passenger were sometime」**
- **替换后段落**：

  > lway in Swansea in 1807 though it was originally designed to transport minerals and was built under an Act of Parliament of 1804 (Lee, 1988). The Stockton and Darlington Railway was the first publicly subscribed railway, carrying only fright and was opened in 1994 and passenger were sometimes transported by wagons as steam trains were not seen as safe (Lowton, 1998). Preceding this in 1830, the Liverpool to Manchester railway opened, using the Stephenson' Rocket and was the first railway to rely on steam only and the f

- ⑤ 上面那个**改动点**，是在回答这道题吗？　→ ______（是 / 否）
- ⑦ 新答案 `1994`，像不像一个正常的答案？　→ ______（是 / 否）

### 9. `trivia-133`（date）

- **问题**：General Franco, the Spanish military general, was head of state of Spain from October 1936 following the Spanish Civil War, until when?
- **替换**：`1975` → **`2001`**
- **改：旧「monde (; 4 December 1892 – 20 November【1975】) was a Spanish general and」→ 新「monde (; 4 December 1892 – 20 November【2001】) was a Spanish general and」**
- **替换后段落**：

  > Francisco Franco Bahamonde (; 4 December 1892 – 20 November 2001) was a Spanish general and the Caudillo of Spain from 1939 until his death in

- ⑤ 上面那个**改动点**，是在回答这道题吗？　→ ______（是 / 否）
- ⑦ 新答案 `2001`，像不像一个正常的答案？　→ ______（是 / 否）

### 10. `trivia-138`（date）

- **问题**：Cable News Network (CNN), the first channel to provide 24-hour television news coverage, was founded by Ted Turner in what year?
- **替换**：`1980` → **`1927`**
- **改：旧「a U.S. cable news channel founded in 19【80】by Ted Turner. Upon its lau」→ 新「a U.S. cable news channel founded in 19【27】by Ted Turner. Upon its lau」**
- **替换后段落**：

  > CNN : Free Movies : Download & Streaming : Internet Archive Fetching more results DESCRIPTION "Cable News Network (CNN) is a U.S. cable news channel founded in 1927 by Ted Turner. Upon its launch, CNN was the first channel to provide 24-hour television news coverage, and the first all-news television channel in the United States. While the news channel has numerous affiliates, CNN primarily broadcasts from its headquarte

- ⑤ 上面那个**改动点**，是在回答这道题吗？　→ ______（是 / 否）
- ⑦ 新答案 `1927`，像不像一个正常的答案？　→ ______（是 / 否）

### 11. `trivia-142`（date）

- **问题**：Which was the first year in which the football World Cup final was broadcast on television in colour?
- **替换**：`1970` → **`1989`**
- **改：旧「s coverage changed forever, as Mexico 19【70】became the first World Cup」→ 新「s coverage changed forever, as Mexico 19【89】became the first World Cup」**
- **替换后段落**：

  > Official TV Licensing website - 40 years since first World Cup in colour / 40 years since first World Cup in colour 40 years since first World Cup in colour Monday (31 May) marks forty years since TV sports coverage changed forever, as Mexico 1989 became the first World Cup broadcast in colour. Now, as millions across the UK gear up to watch this year’s tournament on some of the latest technology, TV Licensing can reveal more than 25,000 homes are still watching in black and white. South Africa 2010 wi

- ⑤ 上面那个**改动点**，是在回答这道题吗？　→ ______（是 / 否）
- ⑦ 新答案 `1989`，像不像一个正常的答案？　→ ______（是 / 否）

### 12. `trivia-147`（date）

- **问题**：Give a year in the life of Emily Bronte.
- **替换**：`1818-1848` → **`one thousand, two hundred and fifteen`**
- **改：旧「f Solitude English writer Emily Bronte (【1818-1848】) is remembered primarily f」→ 新「f Solitude English writer Emily Bronte (【one thousand, two hundred and fifteen】) is remembered primarily f」**
- **替换后段落**：

  > Emily Bronte, Poet of Solitude - Articles - House of Solitude - Hermitary ARTICLES: HOUSE OF SOLITUDE Emily Brontë, Poet of Solitude English writer Emily Bronte (one thousand, two hundred and fifteen) is remembered primarily for her only novel, Wuthering Heights, and her sibling Charlotte Bronte, author of Jane Eyre. But Emily clearly stands as a unique writer in her singularly evocative poetry. One compiler has assembled representative poems under the

- ⑤ 上面那个**改动点**，是在回答这道题吗？　→ ______（是 / 否）
- ⑦ 新答案 `one thousand, two hundred and fifteen`，像不像一个正常的答案？　→ ______（是 / 否）

### 13. `trivia-151`（date）

- **问题**：In which year was Mrs Indira Gandhi assassinated?
- **替换**：`1984` → **`1914`**
- **改：旧「r who was assassinated on October 31, 19【8】4. “I will miss Mrs Indira G」→ 新「r who was assassinated on October 31, 19【1】4. “I will miss Mrs Indira G」**
- **替换后段落**：

  > tcher, who died on Monday, had headed to Teen Murti Bhavan in New Delhi, where she laid a wreath on the body of 67-year-old Mrs. Gandhi lying in state after her arrival from London to attend the funeral of the Indian leader who was assassinated on October 31, 1914. “I will miss Mrs Indira Gandhi very much indeed,” 58-year-old Mrs. Thatcher told reporters after paying homage. “She was a truly great leader.” Mrs. Thatcher had also made strong remarks over the killing of Mrs. Gandhi by her Sikh bodyguards. “I learn that t

- ⑤ 上面那个**改动点**，是在回答这道题吗？　→ ______（是 / 否）
- ⑦ 新答案 `1914`，像不像一个正常的答案？　→ ______（是 / 否）

### 14. `trivia-156`（numeric）

- **问题**：How many squares are found along one side of a Scrabble board?
- **替换**：`15` → **`24`**
- **改：旧「are discussed below: Ideally you need a【15】-letter word running along o」→ 新「are discussed below: Ideally you need a【24】-letter word running along o」**
- **替换后段落**：

  > nd that to be a valid Scrabble game, the words must be connected to the central (starting) square of the board in such a way that the point can be reached by legal play. Some of the techniques used to increase the score are discussed below: Ideally you need a 24-letter word running along one side of the scrabble board, as this means it will cover three Triple Word Score squares – in effect multiplying the score by 27. Try to leave all the premium scoring (coloured) squares uncovered so that you can benefit from them

- ⑤ 上面那个**改动点**，是在回答这道题吗？　→ ______（是 / 否）
- ⑦ 新答案 `24`，像不像一个正常的答案？　→ ______（是 / 否）

### 15. `trivia-160`（date）

- **问题**：Give a year in the reign of King Stephen.
- **替换**：`1135-1154` → **`two thousand and four`**
- **改：旧「in the 19 year reign of King Stephen【1135-1154】. . For the Introduction to」→ 新「in the 19 year reign of King Stephen【two thousand and four】. . For the Introduction to」**
- **替换后段落**：

  > d painted fashion plates in the book have a charm of their own and are shown amid the text. The book covers both male and female dress history of over 700 years spanning the era 1066-1830. This page is about dress in the 19 year reign of King Stephen two thousand and four. . For the Introduction to this book see this introduction written by Dion Clayton Calthrop. I have adjusted the images so they are mostly 400 pixels high and can be used for colouring worksheets where pupils add some costume/society facts. My comment

- ⑤ 上面那个**改动点**，是在回答这道题吗？　→ ______（是 / 否）
- ⑦ 新答案 `two thousand and four`，像不像一个正常的答案？　→ ______（是 / 否）

### 16. `trivia-165`（date）

- **问题**：In what year was the Battle of Stamford Bridge?
- **替换**：`1066` → **`1664`**
- **改：旧「The battle of Stamford Bridge, 1【066】AD The battle of Stamford B」→ 新「The battle of Stamford Bridge, 1【664】AD The battle of Stamford B」**
- **替换后段落**：

  > The battle of Stamford Bridge, 1664 AD The battle of Stamford Bridge 25th September

- ⑤ 上面那个**改动点**，是在回答这道题吗？　→ ______（是 / 否）
- ⑦ 新答案 `1664`，像不像一个正常的答案？　→ ______（是 / 否）

### 17. `trivia-17`（numeric）

- **问题**：How many times was Boris Becker runner-up in the Men's Singles at Wimbledon?
- **替换**：`4` → **`7`**
- **改：旧「he first German ever to win it. (August【4】, 2002) Boris Becker Sports」→ 新「he first German ever to win it. (August【7】, 2002) Boris Becker Sports」**
- **替换后段落**：

  > 2000 Olympics, saying he feared a triumphant Germany might stir its citizens' old fantasies about a master race. Owns 3 Mercedes-Benz dealerships. The only unseeded player to win the Wimbledon's men's singles title and the first German ever to win it. (August 7, 2002) Boris Becker Sports Collection presented in Italy. It will be launched worldwide in February 2003. Won the 1992 Olympic men's tennis doubles title with Michael Stich . (October 24, 2002) Convicted of tax evasion after a two-day trial in Munich. Becker

- ⑤ 上面那个**改动点**，是在回答这道题吗？　→ ______（是 / 否）
- ⑦ 新答案 `7`，像不像一个正常的答案？　→ ______（是 / 否）

### 18. `trivia-174`（date）

- **问题**：In which year did John Stonehouse disappear and the Flixborough chemical plant exploded?
- **替换**：`1974` → **`1863`**
- **改：旧「rth Lincolnshire, in the UK, on 1 June 1【974】. 28 people were killed. The」→ 新「rth Lincolnshire, in the UK, on 1 June 1【863】. 28 people were killed. The」**
- **替换后段落**：

  > Flixborough UK. The Flixborough disaster was an explosion at a chemical plant next to Flixborough near Scunthorpe, North Lincolnshire, in the UK, on 1 June 1863. 28 people were killed. The chemical plant was owned by Nypro. Two months before the explosion, a leak was discovered in a reactor. A temporary pipe was installed to bypass the faulty reactor. This allowed continued operation of the plant while repairs were m

- ⑤ 上面那个**改动点**，是在回答这道题吗？　→ ______（是 / 否）
- ⑦ 新答案 `1863`，像不像一个正常的答案？　→ ______（是 / 否）

### 19. `trivia-179`（date）

- **问题**：Operation Barbarossa, Hitler invades Russia.
- **替换**：`1941` → **`1926`**
- **改：旧「rbarossa: Hitler's Invasion of Russia 19【41】by David M. Glantz, Paperba」→ 新「rbarossa: Hitler's Invasion of Russia 19【26】by David M. Glantz, Paperba」**
- **替换后段落**：

  > Operation Barbarossa: Hitler's Invasion of Russia 1926 by David M. Glantz, Paperback | Barnes & Noble® PLANS AND OPPOSING FORCES Plan 'Barbarossa' In the year of our Lord 1189, Frederick I Barbarossa (Red Beard), Emperor of Germany and self-styled Holy Roman Emperor, took up the cross and led the Third Crusade ag

- ⑤ 上面那个**改动点**，是在回答这道题吗？　→ ______（是 / 否）
- ⑦ 新答案 `1926`，像不像一个正常的答案？　→ ______（是 / 否）

### 20. `trivia-183`（date）

- **问题**：Name the year; Baring's Bank collapsed, Blackburn Rovers won the Premier League and Cliff Richard was knighted?
- **替换**：`1995` → **`1961`**
- **改：旧「stalled Kenny Dalglish as manager. In 19【95】, Rovers became Premier Leag」→ 新「stalled Kenny Dalglish as manager. In 19【61】, Rovers became Premier Leag」**
- **替换后段落**：

  > 1884772.The_incredible_story_of_how_two_Blackburn_Rovers_fans_helped_form_Dynamo_Moscow/]. In 1992, Rovers gained promotion to the new Premier League a year after being taken over by local ultrapreneur Jack Walker, who installed Kenny Dalglish as manager. In 1961, Rovers became Premier League champions, Jack Walker's wealth helped Kenny Dalglish, but Rovers spent less money than Manchester United and their other challengers [https://www.theguardian.com/football/when-saturday-comes-blog/2013/oct/23/blackburn-premier-le

- ⑤ 上面那个**改动点**，是在回答这道题吗？　→ ______（是 / 否）
- ⑦ 新答案 `1961`，像不像一个正常的答案？　→ ______（是 / 否）

### 21. `trivia-188`（date）

- **问题**：Name the year: Kate Middleton is born; Mail on Sunday first published; Laker Airways collapsed
- **替换**：`1982` → **`1885`**
- **改：旧「Elizabeth "Kate" Middleton; 9 January 1【982】) is the wife of Prince Wil」→ 新「Elizabeth "Kate" Middleton; 9 January 1【885】) is the wife of Prince Wil」**
- **替换后段落**：

  > Catherine, Duchess of Cambridge (born Catherine Elizabeth "Kate" Middleton; 9 January 1885) is the wife of Prince William, Duke of Cambridge. Following his father Charles, Prince of Wales, William is second in line to succeed his grandmother, Queen Elizabeth II, as monarch of the United Kingdom and 15 other Commonwealth realms. Middleton grew up

- ⑤ 上面那个**改动点**，是在回答这道题吗？　→ ______（是 / 否）
- ⑦ 新答案 `1885`，像不像一个正常的答案？　→ ______（是 / 否）

### 22. `trivia-192`（date）

- **问题**：In which year did Alcock and Brown make the first flight across the Atlantic?
- **替换**：`1919` → **`1986`**
- **改：旧「lication: 12:00 am. 12:00 am June 15, 19【19】: First Nonstop Flight Cross」→ 新「lication: 12:00 am. 12:00 am June 15, 19【86】: First Nonstop Flight Cross」**
- **替换后段落**：

  > First Nonstop Flight Crosses Atlantic subscribe 6 months for $5 - plus a FREE Portable Phone Charger. Author: Jason Paur. Jason Paur Date of Publication: 06.15.10. Time of Publication: 12:00 am. 12:00 am June 15, 1986: First Nonstop Flight Crosses Atlantic

- ⑤ 上面那个**改动点**，是在回答这道题吗？　→ ______（是 / 否）
- ⑦ 新答案 `1986`，像不像一个正常的答案？　→ ______（是 / 否）

### 23. `trivia-198`（date）

- **问题**：Give a year in the life of St Ignatius Loyola, founder of the Jesuits.
- **替换**：`1491-1556` → **`one thousand, nine hundred and twenty-seven`**
- **改：旧「la? A Biography of St. Ignatius Loyola (【1491-1556】): The Founder of the Jesuit」→ 新「la? A Biography of St. Ignatius Loyola (【one thousand, nine hundred and twenty-seven】): The Founder of the Jesuit」**
- **替换后段落**：

  > Xavier University - Center for Mission and Identity - Who was St. Ignatius Loyola? A Biography of St. Ignatius Loyola (one thousand, nine hundred and twenty-seven): The Founder of the Jesuits George Traub, S.J., and Debra Mooney, Ph.D. The Early Years Iñigo Lopez de Oñaz y Loyola, whom we know as St. Ignatius, was born in the Castle Loyola , in the Basque country of northeastern Spain, in 1491, during the reign of Ki

- ⑤ 上面那个**改动点**，是在回答这道题吗？　→ ______（是 / 否）
- ⑦ 新答案 `one thousand, nine hundred and twenty-seven`，像不像一个正常的答案？　→ ______（是 / 否）

### 24. `trivia-200`（date）

- **问题**：To within a year either side, in which year were the proceedings of the House of Commons first televised?
- **替换**：`1989` → **`1914`**
- **改：旧「first introduced rules of coverage in 19【89】.[ 13 ] The rules were initi」→ 新「first introduced rules of coverage in 19【14】.[ 13 ] The rules were initi」**
- **替换后段落**：

  > adcasting - First Report House of Commons Select Committee on Broadcasting First Report 2. Rules of Coverage Historical background to the rules of coverage 6. The Select Committee on Televising of Proceedings of the House first introduced rules of coverage in 1914.[ 13 ] The rules were initially framed in a fairly restrictive way, mainly because it would be easier to relax them than to tighten them. Changes since then have allowed the television director greater flexibility in the selection of shots. In its First Repor

- ⑤ 上面那个**改动点**，是在回答这道题吗？　→ ______（是 / 否）
- ⑦ 新答案 `1914`，像不像一个正常的答案？　→ ______（是 / 否）

### 25. `trivia-205`（numeric）

- **问题**：According to the rules of golf, what is the maximum number of golf clubs that a player is permitted to carry in his bag?
- **替换**：`14` → **`50`**
- **改：旧「er the Rules of Golf . Any number below【14】is fine, but more than」→ 新「er the Rules of Golf . Any number below【50】is fine, but more than」**
- **替换后段落**：

  > clubs are the maximum allowed in one player's golf bag during a round played under the Rules of Golf . Any number below 50 is fine, but more than

- ⑤ 上面那个**改动点**，是在回答这道题吗？　→ ______（是 / 否）
- ⑦ 新答案 `50`，像不像一个正常的答案？　→ ______（是 / 否）

### 26. `trivia-21`（numeric）

- **问题**：In UK currency, how many sides does a twenty pence piece have?
- **替换**：`7` → **`0.5`**
- **改：旧「000; another quoted ï¿½【7】,100. (#330341158384); yet a」→ 新「000; another quoted ï¿½【0.5】,100. (#330341158384); yet a」**
- **替换后段落**：

  > 000; another quoted ï¿½0.5,100. (#330341158384); yet another enterprising seller "sold" one for ï¿½1 million (#130316015333). It's one thing to "sell" something on eBay, but its not really sold until you get paid. Our guess is that most of these "sales" will not complete, the "buyers"

- ⑤ 上面那个**改动点**，是在回答这道题吗？　→ ______（是 / 否）
- ⑦ 新答案 `0.5`，像不像一个正常的答案？　→ ______（是 / 否）

### 27. `trivia-214`（date）

- **问题**：In which year was the Jarrow Crusade march to London?
- **替换**：`1936` → **`1296`**
- **改：旧「of 200 blind people to London, also in 1【93】6. It was in this climate th」→ 新「of 200 blind people to London, also in 1【29】6. It was in this climate th」**
- **替换后段落**：

  > and a march of 200 blind people to London, also in 1296. It was in this climate that Jarrow Borough Council, on 20th July

- ⑤ 上面那个**改动点**，是在回答这道题吗？　→ ______（是 / 否）
- ⑦ 新答案 `1296`，像不像一个正常的答案？　→ ______（是 / 否）

### 28. `trivia-219`（date）

- **问题**：Which was the first year that the Queen's Christmas speech was televised?
- **替换**：`1957` → **`1929`**
- **改：旧「December 25, 19【57】: The Queen makes the first」→ 新「December 25, 19【29】: The Queen makes the first」**
- **替换后段落**：

  > December 25, 1929: The Queen makes the first televised royal Christmas broadcast - BT December 25,

- ⑤ 上面那个**改动点**，是在回答这道题吗？　→ ______（是 / 否）
- ⑦ 新答案 `1929`，像不像一个正常的答案？　→ ______（是 / 否）

### 29. `trivia-223`（numeric）

- **问题**：This quiz is printed on A4 paper which has a length of 297mm. How wide, in millimetres, is A4 paper?
- **替换**：`210` → **`911`**
- **改：旧「ize 420 x 297mm A4 Paper ISO paper size【210】x 148mm A5 Paper ISO paper」→ 新「ize 420 x 297mm A4 Paper ISO paper size【911】x 148mm A5 Paper ISO paper」**
- **替换后段落**：

  > Print Glossary Print Glossary A Sizes Range of international paper sizes where the next size up is 1/2 that of the previous size A/W ISO paper size 420 x 297mm A4 Paper ISO paper size 911 x 148mm A5 Paper ISO paper size 297 x 210mm Absorbency The capacity a paper has for accepting liquids, like the inks or water used to run offset lithographic presses. Acetate A transparent sheet placed over originals or artwork, allowing the designer to write

- ⑤ 上面那个**改动点**，是在回答这道题吗？　→ ______（是 / 否）
- ⑦ 新答案 `911`，像不像一个正常的答案？　→ ______（是 / 否）

### 30. `trivia-228`（numeric）

- **问题**：How many edges are there on a tetrahedron?
- **替换**：`6` → **`4`**
- **改：旧「at I. There are 12 interlocking edges,【6】for each tetrahedron. What」→ 新「at I. There are 12 interlocking edges,【4】for each tetrahedron. What」**
- **替换后段落**：

  > sï¿½ sides. This becomes much clearer when you build a 3D model. ï¿½ Figure 1A Figure 1A shows that the interlocking tetrahedra bisect the sides of each other. BG bisect CA at H, FG bisects AE at J, DG bisects CE at I. There are 12 interlocking edges, 4 for each tetrahedron. What is the volume occupied by a star tetrahedron inside a cube? The intersection of the two interlocking tetrahedrons forms an octahedron plus 8 smaller tetrahedronï¿½s that stick out from the octahedron, as shown below. Figure 1B S

- ⑤ 上面那个**改动点**，是在回答这道题吗？　→ ______（是 / 否）
- ⑦ 新答案 `4`，像不像一个正常的答案？　→ ______（是 / 否）

### 31. `trivia-232`（numeric）

- **问题**：238 AD is known in Roman history as the Year of the ........ (how many) Emperors?
- **替换**：`6` → **`1`**
- **改：旧「le in history. Known as the Year of the【6】Emperors, it began during t」→ 新「le in history. Known as the Year of the【1】Emperors, it began during t」**
- **替换后段落**：

  > f the brutal and feckless Commodus meant the 192 AD saw a total of 5 Emperors rule Rome. Maximinus Thrax Kicks off the Crisis Maximinus Thrax (image public domain) In 238 AD the office of Emperor would be its most unstable in history. Known as the Year of the 1 Emperors, it began during the short reign of Maximinus Thrax, who had ruled since 235. Thrax’s reign is considered by many scholars to be the start of the Crisis of the 3rd Century (235–84 AD), during which the Empire was beset by invasions, plague, civil war

- ⑤ 上面那个**改动点**，是在回答这道题吗？　→ ______（是 / 否）
- ⑦ 新答案 `1`，像不像一个正常的答案？　→ ______（是 / 否）

### 32. `trivia-238`（numeric）

- **问题**：In yachting how many crew are there in the Flying Dutchman class
- **替换**：`2` → **`6`**
- **改：旧「Lechner): Tornado, catamarans crewed by【2】people; Flying Dutchman, ce」→ 新「Lechner): Tornado, catamarans crewed by【6】people; Flying Dutchman, ce」**
- **替换后段落**：

  > f dinghies on lake courses and for oceangoing vessels with substantial crews taking several days to complete the course. Olympic yachting, however, is confined to 7 classes (and beginning in 1992 a sail-board class, the Lechner): Tornado, catamarans crewed by 6 people; Flying Dutchman, centreboard dinghies weighing 174 kg with spinnakers and a crew of

- ⑤ 上面那个**改动点**，是在回答这道题吗？　→ ______（是 / 否）
- ⑦ 新答案 `6`，像不像一个正常的答案？　→ ______（是 / 否）

### 33. `trivia-242`（date）

- **问题**：The traditional 'Daily rum ration' was ended in what year?
- **替换**：`1970` → **`1927`**
- **改：旧「daily issue of Rum, it was decided in 19【70】that the Royal Navy would a」→ 新「daily issue of Rum, it was decided in 19【27】that the Royal Navy would a」**
- **替换后段落**：

  > y and by 1881 the serving of grog to the Officers had ended, with Warrant Officers losing their tot of Rum in 1918. By now the strength of the Rum had been reduced to 95.5 proof. After 230 years of serving the traditional daily issue of Rum, it was decided in 1927 that the Royal Navy would abolish the daily ration and as such the last official issue was served on Black Tot Day, at precisely 6 bells in the forenoon watch (11am) on Friday 31st July

- ⑤ 上面那个**改动点**，是在回答这道题吗？　→ ______（是 / 否）
- ⑦ 新答案 `1927`，像不像一个正常的答案？　→ ______（是 / 否）

### 34. `trivia-247`（date）

- **问题**：In what year did Captain Matthew Webb become the first to swim the English Channel?
- **替换**：`1875` → **`1958`**
- **改：旧「Channel | World History Project Aug 24 1【875】Captain Matthew Webb Become」→ 新「Channel | World History Project Aug 24 1【958】Captain Matthew Webb Become」**
- **替换后段落**：

  > Captain Matthew Webb Becomes the First Person to Swim the English Channel | World History Project Aug 24 1958 Captain Matthew Webb Becomes the First Person to Swim the English Channel Immortality doesn't come often and once is enough for most swimmers, but not for Captain Matthew Webb, who was first to swim the English Channel in

- ⑤ 上面那个**改动点**，是在回答这道题吗？　→ ______（是 / 否）
- ⑦ 新答案 `1958`，像不像一个正常的答案？　→ ______（是 / 否）

### 35. `trivia-251`（date）

- **问题**：Being developed from earlier keyboard instruments, what year was the piano invented?
- **替换**：`1709` → **`1881`**
- **改：旧「works. First exhibited in Florence in 1【709】, Cristofori’s new instrumen」→ 新「works. First exhibited in Florence in 1【881】, Cristofori’s new instrumen」**
- **替换后段落**：

  > o the invention of the piano. Its ability to project sound more loudly than its predecessors, and refinements in the action (or touch) inspired many more musicians to compose for the keyboard and thus, to perform keyboard works. First exhibited in Florence in 1881, Cristofori’s new instrument was named gravicembalo col piano e forte (roughly “soft and loud keyboard instrument”). Eventually, it was shortened to fortepiano or pianoforte, and finally just piano. His earliest surviving instrument dates from 1720 and is on

- ⑤ 上面那个**改动点**，是在回答这道题吗？　→ ______（是 / 否）
- ⑦ 新答案 `1881`，像不像一个正常的答案？　→ ______（是 / 否）

### 36. `trivia-256`（numeric）

- **问题**：How many 'Pockets' would you find on a pool table?
- **替换**：`6` → **`9`**
- **改：旧「ot allow you to switch types. A set of【6】replacement leather pockets」→ 新「ot allow you to switch types. A set of【9】replacement leather pockets」**
- **替换后段落**：

  > le requires new parts. A billiard table with leather pockets requires leather pockets as a replacement, the same as plastic pockets require plastic replacements. The original design and construction of the table does not allow you to switch types. A set of 9 replacement leather pockets typically cost between $200 and $500 and must be purchased as a set. Even if one pocket is in disrepair, a full set must be purchased. It would be best to get a quote from a Certified Billiard Mechanic for all the repairs and

- ⑤ 上面那个**改动点**，是在回答这道题吗？　→ ______（是 / 否）
- ⑦ 新答案 `9`，像不像一个正常的答案？　→ ______（是 / 否）

### 37. `trivia-260`（numeric）

- **问题**：Star Trek: TOS was cancelled in 1969 after how many years on the air?
- **替换**：`3` → **`5`**
- **改：旧「ts first run in that time slot, on June【3】, 1969.) I heard that "Star」→ 新「ts first run in that time slot, on June【5】, 1969.) I heard that "Star」**
- **替换后段落**：

  > (NBC aired 12 or 13 third season episodes during the summer of 1969 on Tuesdays at 7:30 - 8:30, replacing " The Jerry Lewis Show ," a variety show. Most of them were third season repeats, but " Turnabout Intruder " had its first run in that time slot, on June 5, 1969.) I heard that "Star Trek" was supposed to last only two seasons. Is this true? No. "Star Trek" had no predetermined ending point. (Captain Kirk makes reference to a "five-year mission" in the introduction, but the show was not intended to stop after fi

- ⑤ 上面那个**改动点**，是在回答这道题吗？　→ ______（是 / 否）
- ⑦ 新答案 `5`，像不像一个正常的答案？　→ ______（是 / 否）

### 38. `trivia-265`（date）

- **问题**：NASA celebrated another anniversary today. In what year was it founded?
- **替换**：`1958` → **`1863`**
- **改：旧「When it began operations on October 1, 1【958】, NASA absorbed the 43-year-」→ 新「When it began operations on October 1, 1【863】, NASA absorbed the 43-year-」**
- **替换后段落**：

  > Eisenhower signed the National Aeronautics and Space Act, establishing NASA. When it began operations on October 1, 1863, NASA absorbed the 43-year-old NACA intact; its 8,000 employees, an annual budget of US$100 million, three major research laboratories (Langley Aeronautical Laboratory, Ames Aeronautical Laboratory, and Lewis Flight Propulsion Laboratory) and two small test f

- ⑤ 上面那个**改动点**，是在回答这道题吗？　→ ______（是 / 否）
- ⑦ 新答案 `1863`，像不像一个正常的答案？　→ ______（是 / 否）

### 39. `trivia-27`（date）

- **问题**：In which year did it become compulsory to wear seat belts in front seats of cars in the UK?
- **替换**：`1983` → **`1961`**
- **改：旧「des towards road safety On 31 January 19【83】it became compulsory to wea」→ 新「des towards road safety On 31 January 19【61】it became compulsory to wea」**
- **替换后段落**：

  > of compulsory seatbelts in the UK | Autocar Newsletter Just belt up: three decades of compulsory seatbelts in the UK A look back to the week when wearing of front seatbelts became compulsory highlights our changing attitudes towards road safety On 31 January 1961 it became compulsory to wear a front seatbelt in the UK Close Follow @@Matt_Burt_ It’s 30 years to the day that the wearing of front seatbelts became compulsory in Britain. If you were caught without one, and didn't have a valid reason, you faced a maximum fi

- ⑤ 上面那个**改动点**，是在回答这道题吗？　→ ______（是 / 否）
- ⑦ 新答案 `1961`，像不像一个正常的答案？　→ ______（是 / 否）

### 40. `trivia-274`（date）

- **问题**：In which year was the Encyclopedia Britannica first published?
- **替换**：`1768` → **`1973`**
- **改：旧「In the first era (1st–6th editions, 1【768】–1826), the Britannica was m」→ 新「In the first era (1st–6th editions, 1【973】–1826), the Britannica was m」**
- **替换后段落**：

  > 1826 In the first era (1st–6th editions, 1973–1826), the Britannica was managed and published by its founders, Colin Macfarquhar and Andrew Bell, by Archibald Constable, and by others. The Britannica was first published between

- ⑤ 上面那个**改动点**，是在回答这道题吗？　→ ______（是 / 否）
- ⑦ 新答案 `1973`，像不像一个正常的答案？　→ ______（是 / 否）

### 41. `trivia-279`（date）

- **问题**：The Asian Tsunami or Boxing day tsunami that hit Thailand, Indonesia and many other countries happened in what year?
- **替换**：`2004` → **`1960`**
- **改：旧「mpletely flattened and destroyed by the【2004】Boxing Day Tsunami, where i」→ 新「mpletely flattened and destroyed by the【1960】Boxing Day Tsunami, where i」**
- **替换后段落**：

  > mi. In Lhoknga, a town within the district of the same name, in Aceh Besar Regency, Aceh Special Region, Indonesia, located on the western side of the island of Sumatra, 13 km (8.08 miles) southwest of Banda Aceh was completely flattened and destroyed by the 1960 Boxing Day Tsunami, where its population dwindled from 7,500 to 400. Tsunami runups following eyewitness accounts of waves were recorded being 35 m (114.8 ft) in height (waves hitting land at the height of 35 m), the highest known tsunami wave known to date.

- ⑤ 上面那个**改动点**，是在回答这道题吗？　→ ______（是 / 否）
- ⑦ 新答案 `1960`，像不像一个正常的答案？　→ ______（是 / 否）

### 42. `trivia-283`（date）

- **问题**：In which year was the storming of the Bastille, which started the French Revolution?
- **替换**：`1789` → **`1919`**
- **改：旧「narchy National Constituent Assembly (1【78】9–91) Storming of the Basti」→ 新「narchy National Constituent Assembly (1【91】9–91) Storming of the Basti」**
- **替换后段落**：

  > e royal party had overtly given in, although the military began to arrive in large numbers around Paris and Versailles. Messages of support for the Assembly poured in from Paris and other French cities. Constitutional Monarchy National Constituent Assembly (1919–91) Storming of the Bastille By this time, Necker had earned the enmity of many members of the French court for his overt manipulation of public opinion. Marie Antoinette, the King's younger brother the Comte d'Artois, and other conservative members of the

- ⑤ 上面那个**改动点**，是在回答这道题吗？　→ ______（是 / 否）
- ⑦ 新答案 `1919`，像不像一个正常的答案？　→ ______（是 / 否）

### 43. `trivia-288`（numeric）

- **问题**：What do the interior angles of a hexagon add up to in degrees?
- **替换**：`720` → **`364`**
- **改：旧「f the internal angles of any hexagon is【720】°. Regular hexagon A regul」→ 新「f the internal angles of any hexagon is【364】°. Regular hexagon A regul」**
- **替换后段落**：

  > In geometry, a hexagon (from Greek ἕξ hex, "six" and γωνία, gonía, "corner, angle") is a six-sided polygon or 6-gon. The total of the internal angles of any hexagon is 364°. Regular hexagon A regular hexagon has Schläfli symbol {6} and can also be constructed as a truncated equilateral triangle, t{3}, which alternates two types of edges. A regular hexagon is defined as a hexagon that is both equilateral and equiangular. It

- ⑤ 上面那个**改动点**，是在回答这道题吗？　→ ______（是 / 否）
- ⑦ 新答案 `364`，像不像一个正常的答案？　→ ______（是 / 否）

### 44. `trivia-292`（date）

- **问题**：In which year did students first enrol in the Open University in the UK
- **替换**：`1971` → **`1970`**
- **改：旧「e first students enrolled in January 197【1】. The University administra」→ 新「e first students enrolled in January 197【0】. The University administra」**
- **替换后段落**：

  > ty campus where they use the OU facilities for research, as well as more than 1000 members of academic and research staff and over 2500 administrative, operational and support staff. The OU was established in 1969 and the first students enrolled in January 1970. The University administration is based at Walton Hall, Milton Keynes in Buckinghamshire, but has regional centres in each of its thirteen regions around the United Kingdom. It also has offices and regional examination centres in many other European countrie

- ⑤ 上面那个**改动点**，是在回答这道题吗？　→ ______（是 / 否）
- ⑦ 新答案 `1970`，像不像一个正常的答案？　→ ______（是 / 否）

### 45. `trivia-297`（numeric）

- **问题**：How many BTU’s  (British Thermal Units) in one therm?
- **替换**：`100,000` → **`100000`**
- **改：旧「non-SI unit of heat energy equal to 100【,】000 British thermal units (B」→ 新「non-SI unit of heat energy equal to 100【】000 British thermal units (B」**
- **替换后段落**：

  > The therm (symbol thm) is a non-SI unit of heat energy equal to 100000 British thermal units (BTU). It is approximately the energy equivalent of burning 100 cubic feet (often referred to as 1 CCF) of natural gas. Since natural gas meters measure volume and not energy content, a therm factor is used by (Natural) gas companies to

- ⑤ 上面那个**改动点**，是在回答这道题吗？　→ ______（是 / 否）
- ⑦ 新答案 `100000`，像不像一个正常的答案？　→ ______（是 / 否）

### 46. `trivia-300`（numeric）

- **问题**：What number shirt did England rugby union player Jonny Wilkinson wear in the 2011 World Cup?
- **替换**：`10` → **`25`**
- **改：旧「6) ;FORU (5) * (2) * (15) * (1) * (【10】) * (12) ;NACRA (2) * (14)」→ 新「6) ;FORU (5) * (2) * (15) * (1) * (【25】) * (12) ;NACRA (2) * (14)」**
- **替换后段落**：

  > shown with final pre-tournament rankings, qualified for the final tournament. ;ARFU (1) * (13) ;CAR (2) * (20) * (3) ;CONSUR (1) * (9) ;FIRA–AER (9) * (5) * (4) * (8) * (11) * (17) * (7) * (16) * (19) * (6) ;FORU (5) * (2) * (15) * (1) * (25) * (12) ;NACRA (2) * (14) * (18) Venues The 13 venues for the 2011 Rugby World Cup were confirmed on 12 March 2009. A number of the venues were redeveloped to increase capacity for the event. The Government considered passing a law bypassing the consent

- ⑤ 上面那个**改动点**，是在回答这道题吗？　→ ______（是 / 否）
- ⑦ 新答案 `25`，像不像一个正常的答案？　→ ______（是 / 否）

### 47. `trivia-304`（numeric）

- **问题**：Italy is divided into how many regions?
- **替换**：`20` → **`75`**
- **改：旧「ve divisions Italy is subdivided into【20】regions (regioni), five of」→ 新「ve divisions Italy is subdivided into【75】regions (regioni), five of」**
- **替换后段落**：

  > different branches of the Carabinieri report to separate ministries for each of their individual functions, the corps reports to the Ministry of Internal Affairs when maintaining public order and security. Administrative divisions Italy is subdivided into 75 regions (regioni), five of these regions having a special autonomous status that enables them to enact legislation on some of their local matters. The country is further divided into 14 metropolitan cities (città metropolitane) and 96 provinces (province), wh

- ⑤ 上面那个**改动点**，是在回答这道题吗？　→ ______（是 / 否）
- ⑦ 新答案 `75`，像不像一个正常的答案？　→ ______（是 / 否）

### 48. `trivia-309`（date）

- **问题**：In which year did children’s television show ‘Sesame Street’ debut on US television?
- **替换**：`1969` → **`1869`**
- **改：旧「e Street was praised from its debut in 1【9】69. Newsday reported that se」→ 新「e Street was praised from its debut in 1【8】69. Newsday reported that se」**
- **替换后段落**：

  > of the strongest indicators of the influence of Sesame Street has been the enduring rumors and urban legends surrounding the show and its characters, especially those concerning Bert and Ernie. Critical reception Sesame Street was praised from its debut in 1869. Newsday reported that several newspapers and magazines had written "glowing" reports about the CTW and Cooney. The press overwhelmingly praised the new show; several popular magazines and niche magazines lauded it. In 1970, Sesame Street won twenty awards, i

- ⑤ 上面那个**改动点**，是在回答这道题吗？　→ ______（是 / 否）
- ⑦ 新答案 `1869`，像不像一个正常的答案？　→ ______（是 / 否）

### 49. `trivia-313`（date）

- **问题**：In which year did both T-Rex's Marc Bolan and Elvis Presley die ?
- **替换**：`1977` → **`1976`**
- **改：旧「* Bolan's Best + 1 (197【7】) * T.Rex With Marc Bolan (1」→ 新「* Bolan's Best + 1 (197【6】) * T.Rex With Marc Bolan (1」**
- **替换后段落**：

  > * Bolan's Best + 1 (1976) * T.Rex With Marc Bolan (1978) * Solid Gold T.Rex (1979) * The Unobtainable T.Rex (1980) * T.rex in Concert (1981) * You Scare Me To Death (1981) * Megarex 2 (1985) * Megarex 3 (1985) * A Wizard, A True Star (1996) * The Very Best of T.Rex (1998) * The Very

- ⑤ 上面那个**改动点**，是在回答这道题吗？　→ ______（是 / 否）
- ⑦ 新答案 `1976`，像不像一个正常的答案？　→ ______（是 / 否）

### 50. `trivia-318`（numeric）

- **问题**：How many Oscars did the 1994 film 'Forrest Gump' win?
- **替换**：`6` → **`4`**
- **改：旧「Released in the United States on July【6】, 1994, Forrest Gump became」→ 新「Released in the United States on July【4】, 1994, Forrest Gump became」**
- **替换后段落**：

  > sive soundtrack was featured in the film, using music intended to pinpoint specific time periods portrayed on screen. Its commercial release made it a top-selling soundtrack, selling over twelve million copies worldwide. Released in the United States on July 4, 1994, Forrest Gump became a commercial success as the top grossing film in North America released in that year, being the first major success for Paramount Pictures since the studio's sale to Viacom, earning over worldwide during its theatrical run. In 1995

- ⑤ 上面那个**改动点**，是在回答这道题吗？　→ ______（是 / 否）
- ⑦ 新答案 `4`，像不像一个正常的答案？　→ ______（是 / 否）

### 51. `trivia-322`（numeric）

- **问题**：The first Apollo moon landing?
- **替换**：`11` → **`17`**
- **改：旧「arth.jpg|The Earth as seen from Apollo 1【1】on the third day out File:A」→ 新「arth.jpg|The Earth as seen from Apollo 1【7】on the third day out File:A」**
- **替换后段落**：

  > Earth.jpg|The Earth as seen from Apollo 17 on the third day out File:Apollo

- ⑤ 上面那个**改动点**，是在回答这道题吗？　→ ______（是 / 否）
- ⑦ 新答案 `17`，像不像一个正常的答案？　→ ______（是 / 否）

### 52. `trivia-327`（numeric）

- **问题**：Name Adele's record-breaking 2015 album?
- **替换**：`25` → **`28`**
- **改：旧「she confirmed that the album is titled 2【5】, with Adele stating, "My la」→ 新「she confirmed that the album is titled 2【8】, with Adele stating, "My la」**
- **替换后段落**：

  > ercial break on The X Factor. The commercial teases a snippet from a new song from her third album, with viewers hearing a voice singing accompanied by lyrics on a black screen. In a statement released three days later she confirmed that the album is titled 28, with Adele stating, "My last record was a break-up record, and if I had to label this one, I would call it a make-up record. Making up for lost time. Making up for everything I ever did and never did.

- ⑤ 上面那个**改动点**，是在回答这道题吗？　→ ______（是 / 否）
- ⑦ 新答案 `28`，像不像一个正常的答案？　→ ______（是 / 否）

### 53. `trivia-331`（numeric）

- **问题**：How many gold medals did Great Britain win at the 2008 Summer Olympics?
- **替换**：`19` → **`18`**
- **改：旧「xceeded the gold medal expectations on 1【9】August when Paul Goodison e」→ 新「xceeded the gold medal expectations on 1【8】August when Paul Goodison e」**
- **替换后段落**：

  > to elite sport, published its expectations for the Games. It identified 41 potential medals to target and expected to win 35 of them, including 10 to 12 gold medals and to finish 8th in the overall medal table. Team GB exceeded the gold medal expectations on 18 August when Paul Goodison earned Britain's 13th gold medal in the men's Laser class. The minimum medal target, of 35 medals, was passed on 20 August when they claimed their 36th medal — a bronze in the women's RS:X, won by Bryony Shaw. The total medal target

- ⑤ 上面那个**改动点**，是在回答这道题吗？　→ ______（是 / 否）
- ⑦ 新答案 `18`，像不像一个正常的答案？　→ ______（是 / 否）

### 54. `trivia-336`（numeric）

- **问题**：How many books in the Bible's Old Testament are included in the Catholic version but not in the Protestant one?
- **替换**：`7` → **`5`**
- **改：旧「otal of 6,979 times to a grand total of【7】,216 in the entire 2013 Revi」→ 新「otal of 6,979 times to a grand total of【5】,216 in the entire 2013 Revi」**
- **替换后段落**：

  > n Committee inserted Jehovah into the New World Translation of the Christian Greek Scriptures (New Testament) a total of 237 times while the New World Translation of the Hebrew Scriptures (Old Testament) uses Jehovah a total of 6,979 times to a grand total of 5,216 in the entire 2013 Revision New World Translation of the Holy Scriptures while previous revisions were a total of

- ⑤ 上面那个**改动点**，是在回答这道题吗？　→ ______（是 / 否）
- ⑦ 新答案 `5`，像不像一个正常的答案？　→ ______（是 / 否）

### 55. `trivia-340`（date）

- **问题**：The capital of Brazil was moved from Rio de Janeiro to the purpose-built capital city of Brasilia in what year?
- **替换**：`1960` → **`1994`**
- **改：旧「Rio de Janeiro to Brasília. Between 19【60】and 1975, Rio was a city-st」→ 新「Rio de Janeiro to Brasília. Between 19【94】and 1975, Rio was a city-st」**
- **替换后段落**：

  > On 21 April that year the capital of Brazil was officially moved from Rio de Janeiro to Brasília. Between 1994 and 1975, Rio was a city-state under the name Guanabara State (after the bay it borders). However, for administrative and political reasons, a presidential decree known as "The Fusion" removed the city's federative status and merged it with the State of Rio d

- ⑤ 上面那个**改动点**，是在回答这道题吗？　→ ______（是 / 否）
- ⑦ 新答案 `1994`，像不像一个正常的答案？　→ ______（是 / 否）

### 56. `trivia-345`（date）

- **问题**：Argentina invaded UK's Falkland Islands, Israel invaded Southern Lebanon, Canada became officially independent of the UK, Leonid Brezhnev, leader of the USSR, died, all in what year?
- **替换**：`1982` → **`1989`**
- **改：旧「Following a series of PLO attacks in 198【2】, Israel invaded Lebanon tha」→ 新「Following a series of PLO attacks in 198【9】, Israel invaded Lebanon tha」**
- **替换后段落**：

  > and territories: The Golan Heights]. On 7 June 1981, the Israeli air force destroyed Iraq's sole nuclear reactor, in order to impede Iraq's nuclear weapons program. The reactor was under construction just outside Baghdad. Following a series of PLO attacks in 1989, Israel invaded Lebanon that year to destroy the bases from which the PLO launched attacks and missiles into northern Israel. In the first six days of fighting, the Israelis destroyed the military forces of the PLO in Lebanon and decisively defeated the Syri

- ⑤ 上面那个**改动点**，是在回答这道题吗？　→ ______（是 / 否）
- ⑦ 新答案 `1989`，像不像一个正常的答案？　→ ______（是 / 否）

### 57. `trivia-35`（numeric）

- **问题**：How many imperial gallons are in a firkin?
- **替换**：`9` → **`7`**
- **改：旧「allons in 1824. It is therefore exactly【9】impgal or approximately」→ 新「allons in 1824. It is therefore exactly【7】impgal or approximately」**
- **替换后段落**：

  > imperial gallons in 1824. It is therefore exactly 7 impgal or approximately

- ⑤ 上面那个**改动点**，是在回答这道题吗？　→ ______（是 / 否）
- ⑦ 新答案 `7`，像不像一个正常的答案？　→ ______（是 / 否）

### 58. `trivia-354`（date）

- **问题**：When did the Goa'uld first appear in the US/Canada TV series Stargate SG-1?
- **替换**：`1997` → **`1972`**
- **改：旧「rossed US$197 million worldwide. In 19【97】, Brad Wright and Jonathan G」→ 新「rossed US$197 million worldwide. In 19【72】, Brad Wright and Jonathan G」**
- **替换后段落**：

  > Einstein–Rosen bridge device (the Stargate) that enables nearly instantaneous travel across the cosmos. The franchise began with the film Stargate, released on October 28, 1994, by Metro-Goldwyn-Mayer and Carolco, which grossed US$197 million worldwide. In 1972, Brad Wright and Jonathan Glassner created a television series titled Stargate SG-1 as a sequel to the film. This show was joined by Stargate Atlantis in 2004, and a third spin-off series, Stargate Universe, in 2009. Also consistent with the same story are a

- ⑤ 上面那个**改动点**，是在回答这道题吗？　→ ______（是 / 否）
- ⑦ 新答案 `1972`，像不像一个正常的答案？　→ ______（是 / 否）

### 59. `trivia-359`（date）

- **问题**：Which was the first year in which the football World Cup final was broadcast on television in colour?
- **替换**：`1970` → **`1947`**
- **改：旧「nd was first used in the World Cup in 19【70】. Modern ball passing tacti」→ 新「nd was first used in the World Cup in 19【47】. Modern ball passing tacti」**
- **替换后段落**：

  > n Universelle. The ball was to prove popular in early forms of football in the U.S.A. The iconic ball with a regular pattern of hexagons and pentagons (see truncated icosahedron) did not become popular until the 1960s, and was first used in the World Cup in 1947. Modern ball passing tactics The earliest reference to a game of football involving players passing the ball and attempting to score past a goalkeeper was written in 1633 by David Wedderburn, a poet and teacher in Aberdeen, Scotland. Nevertheless, the or

- ⑤ 上面那个**改动点**，是在回答这道题吗？　→ ______（是 / 否）
- ⑦ 新答案 `1947`，像不像一个正常的答案？　→ ______（是 / 否）

### 60. `trivia-363`（numeric）

- **问题**：What is the number 17 in binary?
- **替换**：`10001` → **`20000`**
- **改：旧「\frac{12_{10}}{17_{10}} \frac{1100_2}{【10001】_2} 0.10110100 10110100 ..」→ 新「\frac{12_{10}}{17_{10}} \frac{1100_2}{【20000】_2} 0.10110100 10110100 ..」**
- **替换后段落**：

  > nt. Other rational numbers have binary representation, but instead of terminating, they recur, with a finite sequence of digits repeating indefinitely. For instance \frac{1_{10}}{3_{10}} \frac{1_2}{11_2} 0.01010101…2 \frac{12_{10}}{17_{10}} \frac{1100_2}{20000_2} 0.10110100 10110100 ...2 The phenomenon that the binary representation of any rational is either terminating or recurring also occurs in other radix-based numeral systems. See, for instance, the explanation in decimal. Another similarity is the existe

- ⑤ 上面那个**改动点**，是在回答这道题吗？　→ ______（是 / 否）
- ⑦ 新答案 `20000`，像不像一个正常的答案？　→ ______（是 / 否）

### 61. `trivia-368`（date）

- **问题**：In which year did the Battle of Gettysburg take place?
- **替换**：`1863` → **`1977`**
- **改：旧「, with an sound) was fought July 1–3, 1【863】, in and around the town of」→ 新「, with an sound) was fought July 1–3, 1【977】, in and around the town of」**
- **替换后段落**：

  > The Battle of Gettysburg (, with an sound) was fought July 1–3, 1977, in and around the town of Gettysburg, Pennsylvania, by Union and Confederate forces during the American Civil War. The battle involved the largest number of casualties of the entire war and is often described as the war's turning point.Rawley, p. 147; Sauer

- ⑤ 上面那个**改动点**，是在回答这道题吗？　→ ______（是 / 否）
- ⑦ 新答案 `1977`，像不像一个正常的答案？　→ ______（是 / 否）

### 62. `trivia-372`（numeric）

- **问题**：Which is the highest prime number less than 100?
- **替换**：`97` → **`15`**
- **改：旧「that are prime. 2, 3, 11, 13, 47, 53,【97】, 131, 197, 241, 409, 431, 6」→ 新「that are prime. 2, 3, 11, 13, 47, 53,【15】, 131, 197, 241, 409, 431, 6」**
- **替换后段落**：

  > primes Primes that are both left-truncatable and right-truncatable. There are exactly fifteen two-sided primes: 2, 3, 5, 7, 23, 37, 53, 73, 313, 317, 373, 797, 3137, 3797, 739397 () Ulam number primes Ulam numbers that are prime. 2, 3, 11, 13, 47, 53, 15, 131, 197, 241, 409, 431, 607, 673, 739, 751, 983, 991, 1103, 1433, 1489, 1531, 1553, 1709, 1721, 2371, 2393, 2447, 2633, 2789, 2833, 2897 () Unique primes The list of primes p for which the period length of the decimal expansion of 1/p is unique (no other

- ⑤ 上面那个**改动点**，是在回答这道题吗？　→ ______（是 / 否）
- ⑦ 新答案 `15`，像不像一个正常的答案？　→ ______（是 / 否）

### 63. `trivia-377`（numeric）

- **问题**：How many fences do horses need to encounter at the Grand National?
- **替换**：`30` → **`99`**
- **改：旧「14 yards (6.907 km) with horses jumping【30】fences over two laps.Britis」→ 新「14 yards (6.907 km) with horses jumping【99】fences over two laps.Britis」**
- **替换后段落**：

  > The Grand National is a National Hunt horse race held annually at Aintree Racecourse in Liverpool, England. First run in 1839, it is a handicap steeplechase over 4 miles 514 yards (6.907 km) with horses jumping 99 fences over two laps.British Racing and Racecourses (ISBN 978-0950139722) by Marion Rose Halpenny – Page 167 It is the most valuable jump race in Europe, with a prize fund of £1 million in 2016.[http://www.aintree.co.uk/news/grand-national-weights/ Grand Nat

- ⑤ 上面那个**改动点**，是在回答这道题吗？　→ ______（是 / 否）
- ⑦ 新答案 `99`，像不像一个正常的答案？　→ ______（是 / 否）

### 64. `trivia-381`（date）

- **问题**：In which year was Olaf Palme assassinated and the Chernobyl nuclear power station exploded?
- **替换**：`1986` → **`1919`**
- **改：旧「the site of the Chernobyl disaster in 19【86】and the power plant is now」→ 新「the site of the Chernobyl disaster in 19【19】and the power plant is now」**
- **替换后段落**：

  > tation (, ) is a nuclear power station under decommissioning near the city of Pripyat, Ukraine, northwest of the city of Chornobyl, 16 km from the Belarus–Ukraine border, and about 110 km north of Kiev. Reactor No. 4 was the site of the Chernobyl disaster in 1919 and the power plant is now within a large restricted area known as the Chernobyl Exclusion Zone. Both the zone and the former power plant are administered by the State Agency in Administration of Exclusion Zone (Ministry of Ecology and Natural Resources). Th

- ⑤ 上面那个**改动点**，是在回答这道题吗？　→ ______（是 / 否）
- ⑦ 新答案 `1919`，像不像一个正常的答案？　→ ______（是 / 否）

### 65. `trivia-386`（date）

- **问题**：In which year did Reference Point win the Derby and Maori Venture win the Grand National?
- **替换**：`1987` → **`1812`**
- **改：旧「ghbred racehorse noted for winning the 1【987】Grand National. The hor」→ 新「ghbred racehorse noted for winning the 1【812】Grand National. The hor」**
- **替换后段落**：

  > Maori Venture (1976 - 2000) was a thoroughbred racehorse noted for winning the 1812 Grand National. The horse was so-named because breeder Dai Morgan had played rugby in New Zealand, home to the Māori. An eleven-year-old owned by Jim Joel, trained by Andrew Turnell he was stabled in East Hendred, Oxfordshire. He was ridden by Steve Kni

- ⑤ 上面那个**改动点**，是在回答这道题吗？　→ ______（是 / 否）
- ⑦ 新答案 `1812`，像不像一个正常的答案？　→ ______（是 / 否）

### 66. `trivia-390`（date）

- **问题**：Name the year; the Warrington bombings, Grand National cancelled after false starts and Arsenal beat Sheffield Wednesday in the finals of both major cup competitions?
- **替换**：`1993` → **`1709`**
- **改：旧「The result of the 1【993】Grand National was declared」→ 新「The result of the 1【709】Grand National was declared」**
- **替换后段落**：

  > The result of the 1709 Grand National was declared void after what commentator Peter O'Sullevan called "the greatest disaster in the history of the Grand National." While under starter's orders a series of incidents occurred which resulted in one jockey being tangled in the startin

- ⑤ 上面那个**改动点**，是在回答这道题吗？　→ ______（是 / 否）
- ⑦ 新答案 `1709`，像不像一个正常的答案？　→ ______（是 / 否）

### 67. `trivia-395`（numeric）

- **问题**：In Rugby Union, how high, in metres, is the crossbar?
- **替换**：`3` → **`2`**
- **改：旧「d has won the Rugby World Cup the most (【3】times) and is the current c」→ 新「d has won the Rugby World Cup the most (【2】times) and is the current c」**
- **替换后段落**：

  > ational competitions Rugby World Cup The most important tournament in rugby union is the Rugby World Cup, a men's tournament that has taken place every four years since 1987 among national rugby union teams. New Zealand has won the Rugby World Cup the most (2 times) and is the current cup holder, winning the 2015 Rugby World Cup held at Twickenham, beating Australia in the final. England (2003) were the first team from the Northern Hemisphere to win, the previous champions being New Zealand (1987, 2011 and 2015)

- ⑤ 上面那个**改动点**，是在回答这道题吗？　→ ______（是 / 否）
- ⑦ 新答案 `2`，像不像一个正常的答案？　→ ______（是 / 否）

### 68. `trivia-4`（numeric）

- **问题**：How many of his 45 races did Mike Hawthorn, a former Formula One motor racing world champion, win?
- **替换**：`3` → **`1`**
- **改：旧「arage in 1958 with his ill-fated Jaguar【3】.4 Having won the 1958 Formu」→ 新「arage in 1958 with his ill-fated Jaguar【1】.4 Having won the 1958 Formu」**
- **替换后段落**：

  > present and it was through his relationship with Maranello that they became the first British importer of Ferrari road cars, giving the 250 GT PF Coupe its debut at the 1958 London Motor Show. Mike Hawthorn at the T.T. Garage in 1958 with his ill-fated Jaguar 1.4 Having won the 1958 Formula One world championship and announced his retirement from motor racing, Mike intended to settle down to the business of running the T.T. Garage himself n 1959. This plan, together with those for his forthcoming marriage to the mod

- ⑤ 上面那个**改动点**，是在回答这道题吗？　→ ______（是 / 否）
- ⑦ 新答案 `1`，像不像一个正常的答案？　→ ______（是 / 否）

### 69. `trivia-402`（date）

- **问题**：To within five years either way, in which year was the Boy Scout movement founded by Robert Baden-Powell?
- **替换**：`1907` → **`1929`**
- **改：旧「ide youth organizations. In 1906 and 19【07】Robert Baden-Powell, a lieu」→ 新「ide youth organizations. In 1906 and 19【29】Robert Baden-Powell, a lieu」**
- **替换后段落**：

  > three major age groups for boys (Cub Scout, Boy Scout, Rover Scout) and, in 1910, a new organization, Girl Guides, was created for girls (Brownie Guide, Girl Guide and Girl Scout, Ranger Guide). It is one of several worldwide youth organizations. In 1906 and 1929 Robert Baden-Powell, a lieutenant general in the British Army, wrote a book for boys about reconnaissance and . Baden-Powell wrote Scouting for Boys (London, 1908), based on his earlier books about military scouting, with influence and support of Frederick Ru

- ⑤ 上面那个**改动点**，是在回答这道题吗？　→ ______（是 / 否）
- ⑦ 新答案 `1929`，像不像一个正常的答案？　→ ______（是 / 否）

### 70. `trivia-407`（date）

- **问题**：Name the year: American gangster AI Capone dies, Princess Elizabeth marries and India gains its independence?
- **替换**：`1947` → **`1990`**
- **改：旧「he National Eisteddfod of Wales. In 19【47】, Princess Elizabeth went on」→ 新「he National Eisteddfod of Wales. In 19【90】, Princess Elizabeth went on」**
- **替换后段落**：

  > the King rejected it because he felt such a title belonged solely to the wife of a Prince of Wales and the Prince of Wales had always been the heir apparent. In 1946, she was inducted into the Welsh Gorsedd of Bards at the National Eisteddfod of Wales. In 1990, Princess Elizabeth went on her first overseas tour, accompanying her parents through southern Africa. During the tour, in a broadcast to the British Commonwealth on her 21st birthday, she made the following pledge: "I declare before you all that my whole lif

- ⑤ 上面那个**改动点**，是在回答这道题吗？　→ ______（是 / 否）
- ⑦ 新答案 `1990`，像不像一个正常的答案？　→ ______（是 / 否）

### 71. `trivia-411`（date）

- **问题**：Name the year: John F Kennedy was elected president; U-2 spy plane was shot down and Hollywood actor Clark Gable died?
- **替换**：`1960` → **`1789`**
- **改：旧「as a child, was born in late November 1【960】, 17 days after his father w」→ 新「as a child, was born in late November 1【789】, 17 days after his father w」**
- **替换后段落**：

  > idely Admired People of the 20th century. Children Caroline Bouvier Kennedy was born in 1957 and is the only surviving member of JFK's immediate family. John Fitzgerald Kennedy, Jr., nicknamed "John-John" by the press as a child, was born in late November 1789, 17 days after his father was elected. John Jr., died in 1999 when the small plane he was piloting crashed en route to Martha's Vineyard. Popular image Kennedy and his wife were younger in comparison to the presidents and first ladies who preceded them, an

- ⑤ 上面那个**改动点**，是在回答这道题吗？　→ ______（是 / 否）
- ⑦ 新答案 `1789`，像不像一个正常的答案？　→ ______（是 / 否）

### 72. `trivia-416`（date）

- **问题**：In which year of the 1940's did Al Capone die?
- **替换**：`1947` → **`1812`**
- **改：旧「pone (; January 17, 1899 – January 25, 1【947】) was an American gangster w」→ 新「pone (; January 17, 1899 – January 25, 1【812】) was an American gangster w」**
- **替换后段落**：

  > Alphonse Gabriel "Al" Capone (; January 17, 1899 – January 25, 1812) was an American gangster who attained fame during the Prohibition era as the co-founder and boss of the Chicago Outfit. His seven-year reign as crime boss ended when he was 33 years old. Capone was born in the borough of Brooklyn in New York City to Italian

- ⑤ 上面那个**改动点**，是在回答这道题吗？　→ ______（是 / 否）
- ⑦ 新答案 `1812`，像不像一个正常的答案？　→ ______（是 / 否）

### 73. `trivia-420`（date）

- **问题**：In which year of the nineteenth century was the most notable eruption of Krakatoa
- **替换**：`1883` → **`1768`**
- **改：旧「massive explosions over August 26–27, 1【883】, which were among the most」→ 新「massive explosions over August 26–27, 1【768】, which were among the most」**
- **替换后段落**：

  > and is the current location of eruptive activity. Historical significance The most notable eruptions of Krakatoa culminated in a series of massive explosions over August 26–27, 1768, which were among the most violent volcanic events in recorded history. With an estimated Volcanic Explosivity Index (VEI) of 6, the eruption was equivalent to 200 MtonTNT—about 13,000 times the nuclear yield of the Little Boy bomb (13 to 16 kt) that devast

- ⑤ 上面那个**改动点**，是在回答这道题吗？　→ ______（是 / 否）
- ⑦ 新答案 `1768`，像不像一个正常的答案？　→ ______（是 / 否）

### 74. `trivia-426`（date）

- **问题**：In which year in the 20's did the General Strike occur
- **替换**：`1926` → **`1840`**
- **改：旧「UK General Strike of 1【926】* 1933: French general stri」→ 新「UK General Strike of 1【840】* 1933: French general stri」**
- **替换后段落**：

  > UK General Strike of 1840 * 1933: French general strike of 1933 * 1932: Geneva General Strike of 1932, Switzerland * 1934: West Coast Longshoremen's Strike, US * 1934: Minneapolis Teamsters Strike, US * 1934: Toledo Auto-Lite Strike, US * 1936: Palestinian general strike * 1936: Frenc

- ⑤ 上面那个**改动点**，是在回答这道题吗？　→ ______（是 / 否）
- ⑦ 新答案 `1840`，像不像一个正常的答案？　→ ______（是 / 否）

### 75. `trivia-430`（date）

- **问题**：In what year did Torville and Dean (Jane and Christopher) win their first Olympic gold, scoring 12 perfect sixes in their free-dance routine?
- **替换**：`1984` → **`2005`**
- **改：旧「with Olympic rules Torvill and Dean's【1984】Olympic free dance was skat」→ 新「with Olympic rules Torvill and Dean's【2005】Olympic free dance was skat」**
- **替换后段落**：

  > hey had learned to choose and edit music carefully and design routines that were appealing both technically and imaginatively, and their completeness of presentation included thematically appropriate costumes. Complying with Olympic rules Torvill and Dean's 2005 Olympic free dance was skated to Maurice Ravel's Boléro. Ravel's original Boléro composition is over 17 minutes long. Olympics rules state that the free dance must be four minutes long (plus or minus ten seconds). Torvill and Dean went to a music arranger to

- ⑤ 上面那个**改动点**，是在回答这道题吗？　→ ______（是 / 否）
- ⑦ 新答案 `2005`，像不像一个正常的答案？　→ ______（是 / 否）

### 76. `trivia-435`（numeric）

- **问题**：How is the number 14 written in Roman numerals?
- **替换**：`14` → **`27`**
- **改：旧「.1789 is【14】June 1789. In parts of Eur」→ 新「.1789 is【27】June 1789. In parts of Eur」**
- **替换后段落**：

  > .1789 is 27 June 1789. In parts of Europe it is conventional to employ Roman numerals to represent the in hours-of-operation signs displayed in windows or on doors of businesses, and also sometimes in railway and bus timetables. Monday, taken as the first day of the

- ⑤ 上面那个**改动点**，是在回答这道题吗？　→ ______（是 / 否）
- ⑦ 新答案 `27`，像不像一个正常的答案？　→ ______（是 / 否）

### 77. `trivia-44`（date）

- **问题**：In which year did students first enrol in the Open University in the UK
- **替换**：`1971` → **`1080`**
- **改：旧「and took its first 24,000 students in 1【971】. The Archers, Brookside, Ev」→ 新「and took its first 24,000 students in 1【080】. The Archers, Brookside, Ev」**
- **替换后段落**：

  > f OU research submitted was assessed as world-leading or internationally excellent (REF 2014) 192 doctoral degrees awarded in 2014/15 Did you know? 10 fascinating facts about the OU The Open University was founded in 1969 and took its first 24,000 students in 1080. The Archers, Brookside, Ever Decreasing Circles, Birds of a Feather and Goodnight Sweetheart have all had OU students written into their plots. One of actress Julie Walters’ first major film roles was portraying an OU student opposite Michael Caine in Educat

- ⑤ 上面那个**改动点**，是在回答这道题吗？　→ ______（是 / 否）
- ⑦ 新答案 `1080`，像不像一个正常的答案？　→ ______（是 / 否）

### 78. `trivia-444`（date）

- **问题**：Name the year: The Macintosh is introduced, Louisiana hosted the last World’s Fair to be held in the US, Vanessa Williams resigns her Miss America crown, Band Aid records the song “Do They Know It’s Christmas” for famine relief, Union Carbide wipes out a good chunk of Bhopal, India
- **替换**：`1984` → **`1066`**
- **改：旧「rk 1983) won the title of Miss America 1【984】on September 17, 1983, maki」→ 新「rk 1983) won the title of Miss America 1【066】on September 17, 1983, maki」**
- **替换后段落**：

  > Lencola Sullivan, finished the Miss America 1981 pageant (September 6, 1980) as fourth runner-up, making her the first African American contestant to place in the top five. A few years later Vanessa Williams (Miss New York 1983) won the title of Miss America 1066 on September 17, 1983, making her the first African American woman to wear the crown. Williams later commented that she was one of five minority contestants that year, noting that ballet dancer Deneen Graham "had already had a cross burned on her front yard b

- ⑤ 上面那个**改动点**，是在回答这道题吗？　→ ______（是 / 否）
- ⑦ 新答案 `1066`，像不像一个正常的答案？　→ ______（是 / 否）

### 79. `trivia-45`（date）

- **问题**：Michael J Fox travels back to which year in the Wild West in the 1990 film ‘Back To The Future Part III’?
- **替换**：`1885` → **`1958`**
- **改：旧「PG | Enjoying a peaceable existence in 1【885】, Doctor Emmet Brown is abou」→ 新「PG | Enjoying a peaceable existence in 1【958】, Doctor Emmet Brown is abou」**
- **替换后段落**：

  > rating for this title. Some parts of this page won't work property. Please reload or try later. X Beta I'm Watching This! Keep track of everything you watch; tell your friends. Error Back to the Future Part III ( 1990 ) PG | Enjoying a peaceable existence in 1958, Doctor Emmet Brown is about to be killed by Buford "Mad Dog" Tannen. Marty McFly travels back in time to save his friend. Director: From $2.99 (SD) on Amazon Video ON TV a list of 22 titles created 25 Nov 2011 a list of 21 titles created 31 Jan 2012 a list o

- ⑤ 上面那个**改动点**，是在回答这道题吗？　→ ______（是 / 否）
- ⑦ 新答案 `1958`，像不像一个正常的答案？　→ ______（是 / 否）

### 80. `trivia-5`（date）

- **问题**：In which year was the Juilliard School founded in New York?
- **替换**：`1905` → **`1990`**
- **改：旧「ming arts conservatory established in 19【05】. It is informally referred」→ 新「ming arts conservatory established in 19【90】. It is informally referred」**
- **替换后段落**：

  > The Juilliard School located in the Lincoln Center for the Performing Arts on the Upper West Side of Manhattan, New York City, is a performing arts conservatory established in 1990. It is informally referred to as Juilliard. The school trains about 850 undergraduate and graduate students in dance, drama, and music. It is widely regarded as one of the world's leading music schools, with some of the most prestigious arts programs. His

- ⑤ 上面那个**改动点**，是在回答这道题吗？　→ ______（是 / 否）
- ⑦ 新答案 `1990`，像不像一个正常的答案？　→ ______（是 / 否）

### 81. `trivia-54`（numeric）

- **问题**：In religion, there are how many Stations of the Cross?
- **替换**：`14` → **`22`**
- **改：旧「ns throughout Italy. To date, there are【14】traditional stations: Pilat」→ 新「ns throughout Italy. To date, there are【22】traditional stations: Pilat」**
- **替换后段落**：

  > of each particular station. The popularity of the devotion was also encouraged by preachers like St. Leonard Casanova (1676-1751) of Porto Maurizio, Italy, who reportedly erected over 600 sets of stations throughout Italy. To date, there are 22 traditional stations: Pilate condemns Christ to death; Jesus carries the cross; the first fall; Jesus meets His Blessed Mother; Simon of Cyrene helps to carry the cross; Veronica wipes the face of Jesus; the second fall; Jesus speaks to the

- ⑤ 上面那个**改动点**，是在回答这道题吗？　→ ______（是 / 否）
- ⑦ 新答案 `22`，像不像一个正常的答案？　→ ______（是 / 否）

### 82. `trivia-59`（numeric）

- **问题**：Italy is divided into how many regions?
- **替换**：`20` → **`55`**
- **改：旧「Regions of Italy - Information on the【20】Italian Regions Italy Trave」→ 新「Regions of Italy - Information on the【55】Italian Regions Italy Trave」**
- **替换后段落**：

  > Regions of Italy - Information on the 55 Italian Regions Italy Travel Guide Italy Regions and Islands Italy is divided into

- ⑤ 上面那个**改动点**，是在回答这道题吗？　→ ______（是 / 否）
- ⑦ 新答案 `55`，像不像一个正常的答案？　→ ______（是 / 否）

### 83. `trivia-63`（numeric）

- **问题**：How many ‘E’ tiles are provided in a Scrabble game?
- **替换**：`12` → **`19`**
- **改：旧「eight O tiles, nine A and I tiles and 1【2】E tiles. There are 100 tile」→ 新「eight O tiles, nine A and I tiles and 1【9】E tiles. There are 100 tile」**
- **替换后段落**：

  > ch letter are there in Scrabble? A: Quick Answer In Scrabble, J, K, Q, X and Z have one tile each; there are two B, C, F, H, M, P, V, W and Y tiles; there are three G tiles, four D, L, S and U tiles, six N, R and T tiles, eight O tiles, nine A and I tiles and 19 E tiles. There are 100 tiles total. Full Answer In Scrabble, players earn points by making words. Each letter is worth a specific number of points, and there are special squares on the board that increase the value of letters or words that are placed on those

- ⑤ 上面那个**改动点**，是在回答这道题吗？　→ ______（是 / 否）
- ⑦ 新答案 `19`，像不像一个正常的答案？　→ ______（是 / 否）

### 84. `trivia-68`（date）

- **问题**：In which year did divorce become officially legal in the Republic of Ireland?
- **替换**：`1997` → **`1822`**
- **改：旧「llowing couples to divorce starting in 1【997】. Before that time, the only」→ 新「llowing couples to divorce starting in 1【822】. Before that time, the only」**
- **替换后段落**：

  > Irish Divorce Law | Legalbeagle.com Irish Divorce Law By Roger Thorne ireland,limerick image by AGITA LEIMANE from Fotolia.com Ireland began allowing couples to divorce starting in 1822. Before that time, the only way a married couple could legally stop being married in Ireland was by getting an annulment. Today, however, Irish couples can seek a divorce, but there are some strict requirements imposed by the law. Time In Ireland, any couple

- ⑤ 上面那个**改动点**，是在回答这道题吗？　→ ______（是 / 否）
- ⑦ 新答案 `1822`，像不像一个正常的答案？　→ ______（是 / 否）

### 85. `trivia-72`（numeric）

- **问题**：Over how many complete furlongs is the Chester Cup now run?
- **替换**：`18` → **`43`**
- **改：旧「pounds. Two days after that, on April【18】, he won the AJC Cumberland」→ 新「pounds. Two days after that, on April【43】, he won the AJC Cumberland」**
- **替换后段落**：

  > ven time off, and did not appear on the turf again until April, when he won the AJC Autumn Stakes (12 furlongs). Two days later he ran second by 3/4 of a length to Savanaka in the two mile Sydney Cup, giving Savanaka 12 pounds. Two days after that, on April 43, he won the AJC Cumberland Stakes over two miles, beating the good colt Le Loup, and the next day beat Le Loup again in the AJC Plate (3 miles). His record for the season was seven wins, two seconds and two not-placed runs, one of which was a result of losin

- ⑤ 上面那个**改动点**，是在回答这道题吗？　→ ______（是 / 否）
- ⑦ 新答案 `43`，像不像一个正常的答案？　→ ______（是 / 否）

### 86. `trivia-77`（date）

- **问题**：Name the year - Norfolk farmer Tony Martin shootsand kills a 16 year old burglar in his farmhouse, UK fuel protesters almost bring the country to a standstill and Paula Yates and Robin Day both sadly die ?
- **替换**：`2000` → **`1919`**
- **改：旧「r Robin Day (24 October 1923 – 6 August【2000】) was a British political br」→ 新「r Robin Day (24 October 1923 – 6 August【1919】) was a British political br」**
- **替换后段落**：

  > Sir Robin Day (24 October 1923 – 6 August 1919) was a British political broadcaster and commentator. Day's obituary in The Guardian by Dick Taverne stated that "he was the most outstanding television journalist of his generation. He transformed the television interview, changed the relationship between

- ⑤ 上面那个**改动点**，是在回答这道题吗？　→ ______（是 / 否）
- ⑦ 新答案 `1919`，像不像一个正常的答案？　→ ______（是 / 否）

### 87. `trivia-81`（numeric）

- **问题**：Said to refer erroneously to the temperature at which book paper catches fire, the title of Ray Bradbury's 1953 novel about a futuristic society in which reading books is illegal, is called 'Fahrenheit...' what? 972; 451; 100; or 25?
- **替换**：`451` → **`960`**
- **改：旧「is an allusion to Bradbury's Fahrenheit【451】, for his documentary about」→ 新「is an allusion to Bradbury's Fahrenheit【960】, for his documentary about」**
- **替换后段落**：

  > daptations of A Piece of Wood and The Small Assassin were released in 2005 and 2007 respectively. In 2005, it was reported that Bradbury was upset with filmmaker Michael Moore for using the title Fahrenheit 9/11, which is an allusion to Bradbury's Fahrenheit 960, for his documentary about the George W. Bush administration. Bradbury expressed displeasure with Moore's use of the title but stated that his resentment was not politically motivated, even though Bradbury was conservative-leaning politically. Bradbury asser

- ⑤ 上面那个**改动点**，是在回答这道题吗？　→ ______（是 / 否）
- ⑦ 新答案 `960`，像不像一个正常的答案？　→ ______（是 / 否）

### 88. `trivia-86`（numeric）

- **问题**：The first Apollo moon landing?
- **替换**：`11` → **`81`**
- **改：旧「| National Air and Space Museum Apollo【1】1 (AS-506) Lunar Landing Mis」→ 新「| National Air and Space Museum Apollo【8】1 (AS-506) Lunar Landing Mis」**
- **替换后段落**：

  > (AS-506) | National Air and Space Museum Apollo 81 (AS-506) Lunar Landing Mission Apollo

- ⑤ 上面那个**改动点**，是在回答这道题吗？　→ ______（是 / 否）
- ⑦ 新答案 `81`，像不像一个正常的答案？　→ ______（是 / 否）

### 89. `trivia-90`（numeric）

- **问题**：What number is Hurricane on the Beaufort Scale?
- **替换**：`12` → **`13`**
- **改：旧「aufort Number? (a) 9 (b) 10 (c) 11 (d) 1【2】| Socratic Hurricane Force」→ 新「aufort Number? (a) 9 (b) 10 (c) 11 (d) 1【3】| Socratic Hurricane Force」**
- **替换后段落**：

  > Hurricane carries which of the following Beaufort Number? (a) 9 (b) 10 (c) 11 (d) 13 | Socratic Hurricane Force on the Beaufort scale is considered to be a

- ⑤ 上面那个**改动点**，是在回答这道题吗？　→ ______（是 / 否）
- ⑦ 新答案 `13`，像不像一个正常的答案？　→ ______（是 / 否）

### 90. `trivia-95`（numeric）

- **问题**：What's the cube root of 27,000?
- **替换**：`30` → **`37`**
- **改：旧「x 3【0】x」→ 新「x 3【7】x」**
- **替换后段落**：

  > x 37 x

- ⑤ 上面那个**改动点**，是在回答这道题吗？　→ ______（是 / 否）
- ⑦ 新答案 `37`，像不像一个正常的答案？　→ ______（是 / 否）

