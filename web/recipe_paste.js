/* Taste Check "paste a recipe" parser (Nov 20, 2026). Browser port of recipe_pilot/nlg_parse.py with
   page-specific additions: oils and dried spices go to the page helpers "Oil or fat" and "Dried spices & herbs"
   so their weight still counts; sweeteners added in v.2.7.x; an unmatched line falls back to the ingredient
   search and is marked as a guess. No DOM access, so it can be tested in Node.
   HFP_PASTE.parse(text, names, search) -> [{line, status, item: [name, amount, unit] | null, note}]
   status: ok | approx | guess | skip | none */
(function (G) {
  "use strict";
  const FRAC = { "½": " 1/2", "¼": " 1/4", "¾": " 3/4", "⅓": " 1/3", "⅔": " 2/3", "⅛": " 1/8", "⅜": " 3/8", "⅝": " 5/8", "⅞": " 7/8" };
  const OZ = 28.35, LB = 453.59;
  const NUM = "(?:\\d+\\s+\\d+/\\d+|\\d+/\\d+|\\d+(?:\\.\\d+)?)";
  const QTY = new RegExp(`^\\s*(${NUM})(?:\\s*(?:-|–|to)\\s*(${NUM}))?\\s*`);
  const SIZE = new RegExp(`^\\(\\s*(${NUM})(?:\\s*-\\s*${NUM})?\\s*(ounce|ounces|oz|lb|lbs|pound|pounds|g|gram|grams|ml|fl\\.? oz)\\.?\\s*\\)\\s*`, "i");
  const UNITS = [
    ["fl\\.?\\s*oz\\.?|fluid ounces?", "fl oz"], ["tablespoons?|tbsps?\\.?|tbs\\.?|T\\b", "tbsp"],
    ["teaspoons?|tsps?\\.?|t\\b", "tsp"], ["cups?|c\\.(?=\\s)|c\\b", "cup"], ["ounces?|oz\\.?", "oz"],
    ["pounds?|lbs?\\.?", "lb"], ["kilograms?|kg\\.?", "kg"], ["grams?|g\\b", "g"], ["milliliters?|millilitres?|ml\\b", "ml"],
    ["liters?|litres?|l\\b", "l"], ["pints?|pt\\.?", "pt"], ["quarts?|qt\\.?", "qt"],
    ["cans?|tins?", "can"], ["jars?|bottles?", "jar"], ["packages?|pkgs?\\.?|packets?|envelopes?|boxes?|cartons?", "pkg"],
    ["cloves?", "clove"], ["stalks?|ribs?", "stalk"], ["sprigs?", "sprig"], ["slices?|strips?", "slice"],
    ["pinch(?:es)?|dash(?:es)?", "pinch"], ["bunch(?:es)?|handfuls?", "bunch"], ["heads?", "head"],
    ["sticks?", "stick"], ["scoops?", "scoop"], ["shots?", "shot"], ["inch(?:es)?(?: piece| knob)?(?: of)?|in\\.(?: piece)?", "inch"], ["links?", "each"], ["large|medium|small|whole|lg\\.?|med\\.?|sm\\.?", "each"],
  ].map(([p, c]) => [new RegExp(`^(?:${p})\\s+`, "i"), c]);

  function num(s) {
    s = s.trim();
    if (s.includes(" ") && s.includes("/")) { const [a, b] = s.split(/\s+(.+)/); return parseFloat(a) + num(b); }
    if (s.includes("/")) { const [n, d] = s.split("/"); return parseFloat(n) / parseFloat(d); }
    return parseFloat(s);
  }
  function parseLine(line) {
    let t = line;
    for (const k in FRAC) t = t.split(k).join(FRAC[k]);
    t = t.replace(/^[\s\-–•*·•]+/, "").replace(/\s+/g, " ").trim();
    t = t.replace(/^(a |one )?(pinch|dash)(es)? of /i, "1 pinch ");   // "Pinch of salt" -> 1 pinch
    let qty = null, m = QTY.exec(t);
    if (m) { const a = num(m[1]), b = m[2] ? num(m[2]) : null; qty = b ? (a + b) / 2 : a; t = t.slice(m[0].length); }
    let size = null; const s = SIZE.exec(t);
    if (s) { const v = num(s[1]), u = s[2].toLowerCase(); size = v * (/^(oun|oz|fl)/.test(u) ? OZ : /^(lb|pou)/.test(u) ? LB : 1); t = t.slice(s[0].length); }
    let unit = null;
    for (const [rx, c] of UNITS) { const mm = rx.exec(t + " "); if (mm) { unit = c; t = t.slice(Math.min(mm[0].length, t.length)); break; } }
    t = t.trim().replace(/^of\s+/i, "");
    return { qty, unit, size, text: t.toLowerCase() };
  }

  // ingredient text -> database name; "*" = approximation (closest entry); first match wins
  const MAP = [
    // Nov 21, 2026, from the 460-recipe real-world test (tests/paste_realworld.py). "!" = don't add; the text is the reason.
    // Condensed canned soups (USDA SR Legacy, added Nov 21, 2026), read as sold, before any added water or milk
    ["soup mix|dry soup|onion soup|ramen|bouillon soup", "!dry soup mixes aren't in the database yet, so their salt would be missed"],
    ["(ready[- ]to[- ]serve|chunky|prepared|diluted|home-?made|homestyle).*soup|soup.*(ready[- ]to[- ]serve|prepared|diluted)", "!only condensed (undiluted) canned soups are in the database; add broth, milk or cream for ready-to-serve soup"],
    ["(low|reduced|less)[- ]sodium.*cream of mushroom|cream of mushroom.*(low|reduced|less)[- ]sodium|healthy request.*mushroom", "Soup, Cream of Mushroom (Condensed, Reduced Sodium)"],
    ["(low|reduced|less)[- ]sodium.*cream of chicken|cream of chicken.*(low|reduced|less)[- ]sodium|healthy request.*chicken", "Soup, Cream of Chicken (Condensed, Reduced Sodium)"],
    ["(low|reduced|less)[- ]sodium.*tomato soup|tomato soup.*(low|reduced|less)[- ]sodium|healthy request.*tomato", "Soup, Tomato (Condensed, Reduced Sodium)"],
    ["cream of mushroom", "Soup, Cream of Mushroom (Condensed)"], ["cream of chicken", "Soup, Cream of Chicken (Condensed)"],
    ["cream of celery", "Soup, Cream of Celery (Condensed)"], ["cream of potato", "Soup, Cream of Potato (Condensed)"],
    ["(cheddar |nacho |fiesta )?cheese soup|broccoli cheese soup", "Soup, Cheese (Condensed)*"],
    ["tomato soup|cream of tomato", "Soup, Tomato (Condensed)"], ["chicken noodle soup", "Soup, Chicken Noodle (Condensed)"],
    ["\\bsoup\\b", "!this canned soup isn't in the database yet (we have cream of mushroom, chicken, celery and potato, tomato, cheese and chicken noodle)"],
    ["cake mix|brownie mix|baking mix|bisquick|muffin mix|pancake mix|cookie mix|stuffing mix", "!boxed mixes aren't in the database; enter flour, sugar and salt separately"],
    ["frosting|\\bicing\\b(?! sugar)", "!frosting isn't in the database (it's mostly sugar); add the sugar instead"],
    ["gelatin|jell-?o|pudding mix|instant pudding", "!gelatin and pudding mixes aren't in the database"],
    ["liqueur|liquor|kahlua|brandy|cognac|\\brum\\b|vodka|whisk(e)?y|bourbon|tequila|\\bgin\\b|schnapps|amaretto", "!spirits and liqueurs aren't in the database yet"],
    ["ginger ale|lemon-?lime soda|sprite|7-?up|root beer|club soda|seltzer|tonic water|sparkling water", "!soft drinks other than cola aren't in the database yet (plain soda water barely matters)"],
    ["corned beef|pastrami", "!corned beef isn't in the database yet (it's far saltier than fresh beef)"],
    ["\\bgravy\\b", "!gravy isn't in the database yet"],
    ["tamarind", "!tamarind isn't in the database yet"],
    ["swiss chard|\\bchard\\b", "!chard isn't in the database yet"],
    ["mixed vegetables|frozen vegetables|cooked vegetables|vegetable medley", "!mixed vegetables aren't in the database; add each vegetable on its own line"],
    ["black-?eyed peas?|split peas?|cowpeas?", "!dried peas and black-eyed peas aren't in the database yet"],
    ["(snap|snow|sugar snap) peas?|mange ?tout", "Snap Pea"],
    ["cream[- ]style corn|creamed corn", "Corn (Canned)*"],
    ["steak (seasoning|spice|rub)|montreal|cajun seasoning|creole seasoning|old bay|taco seasoning|fajita seasoning|seasoning blend|\\brub\\b", "Dried spices & herbs*"],
    ["cayenne|red pepper (powder|flakes)|ground red pepper|(ground|crushed|dried) (hot|red|chili|chile) peppers?|chili powder|chile powder|paprika", "Dried spices & herbs"],
    ["(stock|broth|bouillon|consomm[eé]) (powder|granules?|base|paste|concentrate)", "Bouillon"],
    ["coconut cream|cream of coconut", "Coconut Milk*"],
    ["pork (steaks?|chops?|loin|tenderloin|shoulder|butt|roast)", "Pork"],
    ["canned .*salmon|salmon.*\\bcanned\\b", "Fish, Salmon (Canned)"],
    ["honeydew|cantaloupe|(?<!water)\\bmelon", "!melon isn't in the database yet (only watermelon)"], ["watermelon", "Watermelon"],
    ["(candied|crystallized) ginger", "!candied ginger isn't in the database yet"],
    ["chocolate chips?|chocolate morsels?|semi-?sweet chocolate|milk chocolate|white chocolate", "!sweetened chocolate isn't in the database yet (only 70-85% dark)"],
    ["(shredded|flaked|desiccated|sweetened|grated|toasted) coconut|coconut,? (flakes|shredded|grated)|^coconut$", "!dried coconut isn't in the database yet"],
    ["ranch style beans|baked beans|pork and beans|refried beans", "!seasoned canned beans aren't in the database yet"],
    ["(?<!monk |passion |dragon |star )\\bfruit\\b(?! juice)", "!mixed fruit isn't in the database; add each fruit on its own line"],
    ["ground coffee|coffee grounds|coffee beans?", "!ground coffee (not brewed) isn't in the database"],
    ["peanut butter", "Peanut Butter, Salted"], ["steak sauce|\\ba\\.?1\\b", "Sauce, Steak"],
    ["(red|hot) pepper sauce|pepper sauce", "Sauce, Hot (Tabasco)"],
    ["dill pickles?|pickle relish|\\bpickles?\\b", "Pickles, Dill"], ["\\bapple cider(?! vinegar)|\\bapple juice", "Juice, Apple"],
    ["orange juice|\\boj\\b", "Juice, Orange"], ["grapefruit juice", "Juice, Grapefruit"], ["grape juice", "Juice, Grape"],
    ["peach juice|peach nectar", "Juice, Peach"], ["pomegranate juice", "Juice, Pomegranate"],
    ["cranberry juice", "Juice, Cranberry (Unsweetened)*"],
    ["lemonade|limeade","!lemonade isn't in the database yet; add lemon juice, sugar and water"],
    ["sweetened condensed|condensed milk", "!sweetened condensed milk isn't in the database yet (it's about half sugar)"],
    ["ice cream|gelato|sherbet|frozen custard", "!ice cream isn't in the database yet"],
    ["(almond|soy|oat|rice|cashew|hemp) ?milk(?! powder)", "!plant milks aren't in the database yet (canned coconut milk is)"],
    ["evaporated milk", "Milk, Cow*"],
    ["bouillon cubes?|stock cubes?|cubes? of bouillon|bouillon$", "Beef Stock Cube*"],
    ["bouillon (granules|powder|base|paste)|granulated bouillon|better than bouillon", "Bouillon"],
    ["lemon ?grass|lime lea(f|ves)|kaffir|makrut|dried lime|loomi|celery seed|dry mustard|mustard powder|ground mustard", "Dried spices & herbs"],
    ["lemon pepper", "Dried spices & herbs*"],
    ["(vanilla|fruit|peach|blueberry|strawberry|lemon|raspberry|cherry|flavou?red|frozen|sweetened) yogh?urt", "Yogurt, Plain (Whole Milk)*"],
    ["sour cream", "Sour Cream"], ["margarine", "Butter, Salted*"],
    ["salmon roe|ikura", "Salmon Roe"], ["salmon", "Fish, Salmon (Fresh)|canned-if-can"],
    ["sweet potato|\\byams?\\b", "Sweet Potato"], ["potato chips|crisps", "Potato Chips, Salted"], ["\\bpotato(es)?\\b(?! starch| flakes)", "Potato"],
    ["\\bapples?\\b(?! juice| cider| sauce|sauce)", "Apple"],
    ["(?<!chick ?)\\bpeas\\b|green peas?|sweet peas?|garden peas?", "Green Pea"],
    ["(light|dark)? ?corn syrup", "Tapioca Syrup 42 DE*"],
    ["swiss cheese|emmental|gruy[eè]re|jarlsberg|\\bswiss\\b(?! chard)", "Cheese, Emmental*"], ["gouda", "Cheese, Gouda"], ["manchego", "Cheese, Manchego"],
    ["blue cheese|bleu cheese|gorgonzola|roquefort|stilton", "Cheese, Roquefort*"], ["\\bbrie\\b|camembert", "Cheese, Camembert*"],
    ["colby|mexican (blend|cheese)|taco cheese|cheese blend", "Cheese, Cheddar (Aged One Year)*"],
    // Nov 21, 2026 additions (checked first so "flour tortilla" is not read as flour, etc.)
    ["espresso", "Espresso"], ["instant coffee|coffee granules", "Coffee, Instant (Powder)"], ["\\bcoffee\\b(?! bean| grounds)", "Coffee, Brewed"],
    ["green tea(?! leaves?| powder)", "Tea, Green (Brewed)"], ["black tea|\\btea\\b(?! leaves?| bags?)", "Tea, Black (Brewed)"],
    ["cocoa powder|\\bcocoa\\b|cacao powder", "Cocoa Powder (Unsweetened)"],
    ["dark chocolate|bittersweet chocolate|70% chocolate", "Chocolate, Dark (70-85%)*"], ["\\bcola\\b|\\bcoke\\b|pepsi", "Cola"],
    ["silken tofu", "Tofu, Silken"], ["\\btofu\\b|bean curd", "Tofu, Firm"], ["tahini|tahina", "Tahini"], ["gochujang", "Gochujang"],
    ["doenjang|soybean paste", "Doenjang"], ["fermented black beans?|douchi", "Beans, Black (Fermented)"],
    ["black beans?", "Beans, Black (Canned)"], ["kidney beans?", "Beans, Kidney (Canned)"], ["pinto beans?", "Beans, Pinto (Canned)"],
    ["chick ?peas?|garbanzo", "Chickpeas (Canned)"], ["corn tortillas?", "Tortilla, Corn"], ["tortillas?", "Tortilla, Flour"],
    ["monterey jack|pepper jack|\\bjack cheese", "Cheese, Monterey Jack"], ["provolone", "Cheese, Provolone"],
    ["american cheese|velveeta|cheese singles?|kraft singles?", "Cheese, American (Processed)"], ["ricotta", "Cheese, Ricotta (Whole Milk)"],
    ["sun[- ]?dried tomato", "Tomato (Dried)"], ["tomato paste", "Paste, Tomato"], ["tomato puree|tomato purée|passata", "Paste, Tomato*"],
    ["(no[- ]salt|low[- ]sodium|salt[- ]free|unsalted).*(tomato|pasta|spaghetti|marinara) sauce", "Sauce, Tomato"],
    ["(pasta|spaghetti|marinara|pizza) sauce|tomato sauce|\\bragu\\b|\\bprego\\b", "Sauce, Tomato (Canned)"],
    ["tomato juice|v-?8", "Juice, Tomato"], ["cherry tomato|grape tomato", "Tomato, Cherry (Generic)"],
    ["(crushed|diced|stewed|whole|peeled|canned|italian|plum|san marzano|chopped|petite|fire[- ]roasted).*tomato|tomato.*(canned|with juice|undrained|drained)", "Tomato (Canned)|fresh-if-count"],
    ["tomato", "Tomato, Red (Fresh, Whole)"],
    ["garlic salt", "Salt*"], ["garlic powder|granulated garlic|onion powder|onion flakes|dried onion", "Dried spices & herbs"], ["garlic", "Garlic"],
    ["green onion|scallion|spring onion", "Green Onion"], ["shallot", "Shallot"], ["onion", "Onion"],
    ["celery salt", "Salt*"], ["celery", "Celery"], ["carrot", "Carrot"],
    ["(green|red|yellow|orange|bell) pepper(?!corn| flake)|capsicum", "Green Pepper"],
    ["jalape|chili pepper|chile pepper|serrano|hot pepper(?! sauce)|fresno", "Chili Pepper"],
    ["mushroom", "Mushroom, Button"], ["zucchini", "Zucchini"], ["eggplant|aubergine", "Eggplant"], ["spinach", "Spinach"],
    ["diamond crystal", "Kosher Salt (Diamond Crystal)"], ["morton.*kosher|kosher.*morton", "Kosher Salt (Morton)"], ["kosher salt", "Kosher Salt"], ["sea salt", "Sea Salt"], ["\\bmsg\\b|monosodium glutamate|accent seasoning", "Monosodium Glutamate"],
    ["\\bsalt\\b(?! pork)", "Salt"],
    ["splenda|^equal\\b|equal (sweetener|packets?)|nutrasweet|sweet'?n'? ?low|in the raw|sugar substitute|sweetener packet", "BLEND"],
    ["truvia", "Erythritol*"],
    ["stevia extract|pure stevia|rebaudioside|reb a\\b", "Stevia Extract (Reb A 97%)"], ["\\bstevia\\b", "Stevia Extract (Reb A 97%)*"],
    ["monk fruit extract|luo han guo extract|mogroside", "Monk Fruit Extract (Mogroside V 50%)"],
    ["monk fruit sweetener|lakanto|swerve|erythritol", "Erythritol"], ["monk fruit|luo han guo", "Monk Fruit Extract (Mogroside V 50%)*"],
    ["xylitol", "Xylitol"], ["allulose", "Allulose"],
    ["maltitol", "Maltitol"], ["sorbitol", "Sorbitol"], ["sucralose", "Sucralose"], ["aspartame", "Aspartame"],
    ["acesulfame|ace-?k\\b", "Acesulfame Potassium"],
    ["brown sugar", "Brown Sugar"], ["powdered sugar|confectioners|icing sugar", "Sugar*"], ["\\bsugar\\b(?! substitute)|sugar,", "Sugar"],
    ["honey", "Honey"], ["maple syrup", "Maple Syrup"], ["molasses", "Sugar Cane Molasses"],
    ["parmesan|parmigiano|romano|pecorino|asiago|grana padano", "Cheese, Parmigiano Regianno"],
    ["mozzarella", "Cheese, Mozzarella"], ["cheddar", "Cheese, Cheddar (Aged One Year)*"], ["cottage", "Cheese, Cottage*"],
    ["basil", "Basil"], ["parsley", "Parsley"], ["\\bdill\\b", "Dill"], ["\\bmint\\b", "Mint"], ["coriander leaves|cilantro", "Coriander"],
    ["rice vinegar|rice wine vinegar", "Vinegar, Rice"], ["red wine vinegar|wine vinegar", "Vinegar, Red Wine"], ["balsamic", "Vinegar, Balsamic"], ["cider vinegar", "Vinegar, Apple Cider"],
    ["vinegar", "Vinegar, Distilled White"], ["\\bwine\\b|sherry|marsala|vermouth", "Wine, Generic"],
    ["(low|reduced)[- ]sodium.*(broth|stock)|(broth|stock).*(low|reduced)[- ]sodium", "Broth, Chicken (Low Sodium)*"],
    ["beef (broth|stock|bouillon|consomm)", "Broth, Beef"], ["vegetable (broth|stock|bouillon)", "Broth, Vegetable"],
    ["chicken (broth|stock|bouillon)|\\bbroth\\b|\\bstock\\b", "Broth, Chicken"],
    ["capers?\\b", "Capers"], ["unsalted butter|sweet butter", "Oil or fat"], ["\\bbutter\\b(?!milk)|margarine", "Butter, Salted"],
    ["(heavy cream|whipping cream|half[- ]and[- ]half|light cream|\\bcream\\b)(?! cheese)", "Milk, Cow*"],
    ["\\bfeta\\b", "Cheese, Feta"], ["fontina", "Cheese, Mozzarella*"], ["bouillon cube", "Beef Stock Cube*"],
    ["ground beef|hamburger|beef mince|minced beef|ground chuck|ground round|lean beef", "Hamburger Meat"],
    ["ground pork|pork mince", "Pork"], ["ground turkey|turkey", "Chicken*"], ["chicken", "Chicken"], ["\\bbeef\\b|steak|chuck", "Beef"],
    ["\\bbacon\\b", "Bacon"], ["pancetta|guanciale", "Bacon*"], ["prosciutto", "Ham, Dry-Cured"],
    ["italian sausage|\\bsausage", "Sausage, Italian (Pork)"], ["chorizo|salami|pepperoni|kielbasa", "Sausage, Italian (Pork)*"],
    ["\\bham\\b", "Ham, Dry-Cured*"], ["\\bpork\\b", "Pork"], ["shrimp|prawn", "Shrimp"], ["clam", "Clam*"],
    ["anchov", "Fish, Anchovy (Canned)"], ["tuna", "Fish, Tuna (Fresh)*"],
    ["worcestershire", "Sauce, Worcestershire"], ["soy sauce|\\btamari\\b|shoyu", "Sauce, Soy"], ["fish sauce|nam pla|nuoc mam", "Sauce, Fish"],
    ["ketchup|catsup", "Ketchup"], ["cream cheese", "Cheese, Cream"], ["mayonnaise|\bmayo\b", "Mayonnaise"], ["dijon", "Mustard, Dijon"], ["(yellow|prepared|ballpark|french'?s)? ?mustard(?! seed| green| powder)", "Mustard, Yellow (Prepared)"], ["salsa", "Salsa (Jarred)"], ["tabasco|hot sauce|louisiana", "Sauce, Hot (Tabasco)"], ["hoisin", "Sauce, Hoisin"], ["lemon juice|lemon", "Lemon"], ["lime juice|lime", "Juice, Lime"],
    ["black olive|kalamata|ripe olive", "Olives, Black"], ["green olive|olive(?! oil)", "Olives, Green"],
    ["sour cream", "Sour Cream"], ["greek yogurt", "Yogurt, Greek (Plain, Whole Milk)"], ["yogurt", "Yogurt, Plain (Whole Milk)"],
    ["buttermilk", "Buttermilk (Cultured)"], ["coconut milk", "Coconut Milk"], ["\\bmilk\\b", "Milk, Cow"],
    ["miso", "Miso"], ["kombu", "Seaweed, Kombu"], ["bonito|katsuobushi", "Bonito Flakes"],
    ["\\bwater\\b", "Water"], ["egg yolk", "Egg Yolk"], ["egg white", "Egg White"], ["\\beggs?\\b", "Eggs"],
    ["flour", "Flour, Wheat"], ["lentil", "Lentils"],
    ["\\boil\\b|\\blard\\b|shortening|\\bghee\\b|cooking spray", "Oil or fat"],
    ["oregano|thyme|marjoram|rosemary|bay lea|pepper ?flakes|black pepper|ground pepper|peppercorn|^pepper\\b|cayenne|paprika|cumin|chili powder|cinnamon|nutmeg|allspice|ground cloves?|fennel seed|saffron|turmeric|curry powder|garam masala|ginger powder|ground ginger|italian seasoning|dried herbs?|herbes|seasoning|crushed red pepper|sage|tarragon|cardamom|coriander seed|ground coriander|mustard seed|vanilla|star anise|\\banise\\b|cloves? \\(spice\\)|whole cloves|five.spice|sichuan pepper", "Dried spices & herbs"],
    ["\\bginger\\b", "Ginger"],
    ["\\bcheese\\b", "Cheese, Cheddar (Aged One Year)*"],
  ].map(([p, n]) => [new RegExp(p, "i"), n]);
  const SKIP_FIRST = /\b(zest|rind|peel|wedges?|wheels?)\b|garnish|tortellini|ravioli|gnocchi|wonton|egg roll|spring roll|wrappers?\b|\bwraps?\b|dumpling|noodle(?!s? soup)|pasta|spaghetti|penne|linguine|fettuccine|rigatoni|macaroni|\bbread\b|breadcrumb|\brice\b(?! vinegar| wine)/i;
  const SKIP = /spaghetti|pasta|penne|linguine|fettuccine|rigatoni|macaroni|noodle|\brice\b|bread|cornstarch|baking soda|baking powder|\byeast\b(?!.*extract)|gelatin|zest|garnish|for serving|\bice\b/i;
  const EACH_G = { "Onion": 110, "Garlic": 3, "Tomato, Red (Fresh, Whole)": 123, "Tomato, Cherry (Generic)": 17, "Carrot": 61, "Celery": 40,
    "Green Pepper": 119, "Chili Pepper": 15, "Shallot": 25, "Green Onion": 15, "Mushroom, Button": 18, "Zucchini": 196,
    "Eggplant": 458, "Lemon": 58, "Juice, Lime": 44, "Eggs": 50, "Egg Yolk": 17, "Egg White": 33, "Fish, Anchovy (Canned)": 4,
    "Basil": 0.5, "Parsley": 1, "Olives, Black": 4, "Olives, Green": 4, "Beef Stock Cube": 4, "Tomato (Dried)": 3,
    "Sausage, Italian (Pork)": 75, "Bacon": 28, "Potato": 213, "Sweet Potato": 114, "Apple": 182, "Pickles, Dill": 65, "Tortilla, Flour": 49, "Tortilla, Corn": 24, "Dried spices & herbs": 1 };
  const UNIT_G = { clove: 3, stalk: 40, sprig: 1, slice: 20, pinch: 0.4, bunch: 40, head: 50, stick: 113 };
  const CAN_G = { "Tomato (Canned)": 28 * OZ, "Paste, Tomato": 6 * OZ, "Sauce, Tomato": 8 * OZ, "Sauce, Tomato (Canned)": 8 * OZ,
    "Capers": 3.5 * OZ, "Broth, Vegetable": 14.5 * OZ, "Butter, Salted": 113, "Sausage, Italian (Pork)": LB, "Bacon": LB,
    "Broth, Beef": 14.5 * OZ, "Broth, Chicken": 14.5 * OZ, "Olives, Black": 6 * OZ, "Fish, Anchovy (Canned)": 2 * OZ, "Coconut Milk": 13.5 * OZ, "Cola": 370, "Fish, Salmon (Canned)": 14.75 * OZ, "Pickles, Dill": 16 * OZ, "Corn (Canned)": 14.75 * OZ,
    // condensed soups: the standard 10.75 oz can (USDA SR portion "1 can (10.75 oz)" = 305 g)
    "Soup, Cream of Mushroom (Condensed)": 305, "Soup, Cream of Mushroom (Condensed, Reduced Sodium)": 305, "Soup, Cream of Chicken (Condensed)": 305,
    "Soup, Cream of Chicken (Condensed, Reduced Sodium)": 305, "Soup, Cream of Celery (Condensed)": 305, "Soup, Cream of Potato (Condensed)": 305,
    "Soup, Tomato (Condensed)": 305, "Soup, Tomato (Condensed, Reduced Sodium)": 305, "Soup, Cheese (Condensed)": 305, "Soup, Chicken Noodle (Condensed)": 305,  // Cola: 12 fl oz can (USDA SR 174852)
   
    "Beans, Black (Canned)": 15 * OZ * 0.62, "Beans, Kidney (Canned)": 15 * OZ * 0.62, "Beans, Pinto (Canned)": 15 * OZ * 0.62, "Chickpeas (Canned)": 15 * OZ * 0.62 };  // 15 oz can, ~62% drained solids (approximate, an assumption)
  const VOL = { cup: ["cup", 1], tbsp: ["tbsp", 1], tsp: ["tsp", 1], "fl oz": ["fl oz", 1], ml: ["mL", 1], l: ["L", 1], pt: ["cup", 2], qt: ["cup", 4] };
  const HEADER = /:\s*$|^(for the|ingredients|directions|instructions|method|steps?)\b/i;
  const DESCRIPT = /\b(fresh(ly)?|chopped|minced|diced|sliced|grated|shredded|large|medium|small|finely|roughly|ground|crushed|peeled|packed|to taste|optional|divided|plus more|about|cut into.*|or more)\b/g;

  function toItem(p, name, dens) {
    const approx = name.endsWith("*"), freshIfCount = name.endsWith("|fresh-if-count"), canIfCan = name.endsWith("|canned-if-can");
    name = name.replace(/\*$/, "").split("|")[0];
    const q = p.qty, u = p.unit;
    if (q == null) return [null, "skip", "no amount (\"to taste\")"];
    if (freshIfCount && (u == null || u === "each") && p.size == null) name = "Tomato, Red (Fresh, Whole)";
    if (canIfCan && (u === "can" || u === "jar" || u === "pkg" || p.size != null)) name = "Fish, Salmon (Canned)";
    if (name === "Tomato, Red (Fresh, Whole)" && (p.size != null || u === "can" || u === "jar")) name = "Tomato (Canned)";
    let g = null;
    if (p.size != null) g = q * p.size;
    else if (u === "oz") g = q * OZ; else if (u === "lb") g = q * LB; else if (u === "g") g = q; else if (u === "kg") g = q * 1000;
    else if (u in VOL) {
      if (dens && !(dens(name) > 0)) return [null, "none", "no cup or spoon conversion for this one yet; enter it in grams"];
      return [[name, +(q * VOL[u][1]).toFixed(3), VOL[u][0]], approx ? "approx" : "ok", approx ? APPROX_NOTE[name] || "closest match" : ""];
    }
    else if (u === "can" || u === "jar" || u === "pkg") { if (!(name in CAN_G)) return [null, "none", `don't know the ${u} size`]; g = q * CAN_G[name]; }
    else if (u === "scoop") { if (!name.startsWith("Stevia")) return [null, "none", "scoop size unknown for this one; enter it in grams"]; g = q * 0.025; }   // Pyure stevia label: 1 scoop = 25 mg
    else if (u === "shot") g = q * 29.6;   // 1 shot = 1 fl oz (USDA SR espresso portion 29.6 g)
    else if (u === "inch") return [null, "none", "piece size in inches can't be weighed; enter it in grams"];
    else if (u in UNIT_G) g = q * UNIT_G[u];
    else { if (!(name in EACH_G)) return [null, "none", "add a weight or cup/spoon amount"]; g = q * EACH_G[name]; }
    return [[name, +(g < 1 ? g.toFixed(3) : g.toFixed(1)), "g"], approx ? "approx" : "ok", approx ? APPROX_NOTE[name] || "closest match" : ""];
  }

  const APPROX_NOTE = {
    "Soup, Cheese (Condensed)": "read as plain condensed cheese soup (USDA); cheddar and nacho versions differ a little",
    "Yogurt, Plain (Whole Milk)": "read as plain yogurt; a flavored yogurt's added sugar isn't counted",
    "Tapioca Syrup 42 DE": "read as a 42 DE glucose syrup, close to light corn syrup",
    "Dried spices & herbs": "read as a spice blend with no salt; if your blend contains salt, add the salt on its own line",
    "Cheese, Cheddar (Aged One Year)": "read as cheddar, the closest common cheese in the database",
    "Erythritol": "Truvia-type blends are mostly erythritol; their stevia share isn't counted, so sweetness may read a little low",
    "Stevia Extract (Reb A 97%)": "read as pure stevia extract; tabletop stevia blends are mostly erythritol or dextrose",
    "Monk Fruit Extract (Mogroside V 50%)": "read as pure monk fruit extract (50% mogroside V); blends like Lakanto are mostly erythritol",
  };
  // search guesses may not land on these unless the line itself names them (a guess once read "fresh fruit" as monk fruit extract)
  const GUARDED = /extract|stevia|monk fruit|sucralose|aspartame|acesulfame|erythritol|xylitol|maltitol|sorbitol|allulose|mannitol|salt|glutamate|ajitide|chloride|caffeine|espresso|bouillon|stock cube|roe/i;
  // db (optional): {name: {density}}; used to flag cup/spoon amounts that can't be converted to grams
  function parse(text, names, search, db) {
    const dens = db ? (n => (db[n] || {}).density || 0) : null;
    const have = new Set(names), out = [];
    for (const raw of String(text).split(/\r?\n/)) {
      const line = raw.trim();
      if (!line || HEADER.test(line)) continue;
      const p = parseLine(line);
      if (!p.text) { out.push({ line, status: "none", item: null, note: "no ingredient name" }); continue; }
      if (/\bbones?\b|carcass/i.test(p.text)) { out.push({ line, status: "skip", item: null, note: "bones aren't modelled as meat; add the finished broth instead (e.g. Broth, Beef)" }); continue; }
      // Read the main text first: the first of "X or Y", without (notes). Nov 21, 2026: a word inside a note or
      // a second choice used to win ("ground chuck (... onion ...)" read as onion).
      const first = p.text.split(/\s+\(?or\s+/)[0];
      const bare = first.replace(/\([^)]*\)?/g, " ").replace(/\s+/g, " ").trim() || first;
      if (SKIP_FIRST.test(bare)) { out.push({ line, status: "skip", item: null, note: "barely affects these tastes" }); continue; }
      const mapOf = t => { for (const [rx, n] of MAP) if (rx.test(t)) return n; return null; };
      const guessOf = t => {
        if (!search) return null;
        const clean = t.split(",")[0].replace(/\([^)]*\)?/g, " ").replace(DESCRIPT, " ").replace(/\s+/g, " ").trim();
        let hit = clean ? (search(clean, 1) || [])[0] : null;
        if (hit && GUARDED.test(hit) && !hit.toLowerCase().split(/[^a-z]+/).some(w => w.length > 3 && clean.includes(w) && !/fruit|salt|extract/.test(w))) hit = null;
        return hit;
      };
      let name = mapOf(bare) || mapOf(first), status = null, note = "";
      if (!name && first !== p.text) {
        if (SKIP.test(bare)) { out.push({ line, status: "skip", item: null, note: "barely affects these tastes" }); continue; }
        const g = guessOf(first);
        if (g) { name = g; status = "guess"; note = `best guess: ${g}`; }
      }
      if (!name) name = mapOf(p.text);
      if (name && name.startsWith("!")) { out.push({ line, status: "none", item: null, note: name.slice(1) }); continue; }
      if (name === "BLEND") { out.push({ line, status: "none", item: null, note: "tabletop blend bulked with dextrose or maltodextrin; the label doesn't give the sweetener share, so enter the pure sweetener in grams" }); continue; }
      if (!name && SKIP.test(p.text)) { out.push({ line, status: "skip", item: null, note: "barely affects these tastes" }); continue; }
      if (!name) {
        const g = guessOf(p.text);
        if (g) { name = g; status = "guess"; note = `best guess: ${g}`; }
      }
      if (!name) { out.push({ line, status: "none", item: null, note: "not in the database" }); continue; }
      // Nov 24, 2026: plain "peanut butter" / "potato chips" read as the salted USDA versions; the unsalted rows
      // only when the line (notes included) says unsalted / no salt / salt-free / without salt.
      if (/^(Peanut Butter|Potato Chips), Salted$/.test(name) && /\bunsalted\b|\bno[- ]salt|\bsalt[- ]free\b|without salt/i.test(p.text)) name = name.replace(", Salted", ", Unsalted");
      const base = name.replace(/\*$/, "").split("|")[0];
      if (!have.has(base)) { out.push({ line, status: "none", item: null, note: "not in the database" }); continue; }
      const [item, st, nt] = toItem(p, name, dens);
      out.push({ line, status: item && status ? status : st, item, note: item && status ? note : nt });
    }
    return out;
  }
  G.HFP_PASTE = { parse, parseLine };
})(typeof window !== "undefined" ? window : globalThis);
