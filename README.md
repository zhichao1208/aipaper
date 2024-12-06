# aipaper

## TODO

0. scrape the paper text from link https://jina.ai/reader/

```python
import requests

headers = {
    'Authorization': 'Bearer jina_d01480a20b07474f98c89bd119127e68m3lomIqlR7_SafWUNLV3OHVxQvTr'
}

response = requests.get('https://r.jina.ai/https://example.com', headers=headers)
print(response.text)
```


4. change it to english

8. EPIC: add weekly papaers reviews 
9. chose the paper from the list of search results


# *Respond exactly in the following perfectly formatted JSON structure with no missing fields*:
{
  "task_objective": "string // The complete user-given objective of the task. All details must be included",