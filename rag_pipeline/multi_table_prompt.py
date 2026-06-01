"""
Multi-Table SQL Generation Prompt
Specialized prompt for queries across multiple related tables.
"""

from langchain_core.prompts import ChatPromptTemplate
from typing import List, Dict

MULTI_TABLE_SQL_PROMPT_TEMPLATE = """
You are a Senior Data Architect specializing in PostgreSQL query generation. 
Your objective is to translate natural language questions into highly accurate, executable PostgreSQL queries across multiple related tables.

### CRITICAL INSTRUCTIONS:

1. **Schema Context:**
{schema_context}

2. **Approved Tables & Relationships (STRICT):**
{relationships_context}
   ⚠️ YOU MUST ONLY use these exact relationships for JOIN operations. Do NOT attempt to join on columns not explicitly mapped above.

3. **Column Reference Rules & Quoting (CRITICAL):**
   - Use ONLY columns from the schema above. Do NOT invent columns.
   - For ambiguous columns, use table aliases (e.g., `s.column_name`).
   - If a table name or column name contains spaces or capital letters, it MUST be wrapped in double quotes in the SQL.
     - ❌ Incorrect: SELECT sales amount FROM Sales Data
     - ✅ Correct: SELECT "sales amount" FROM "Sales Data"

4. **CTE Preference for Joins & Aggregations (MANDATORY):**
   Whenever a query requires aggregations (SUM, COUNT) and joins across multiple tables, you MUST avoid nested subqueries and avoid aggregating *after* a JOIN (which causes fan-out errors).
   You must aggregate inside a Common Table Expression (CTE) first, and then JOIN the result.
   
   *Pattern Example:*
   WITH AggregatedSales AS (
       SELECT "customer_id", SUM("amount") as total_sales
       FROM "Sales_Table"
       GROUP BY "customer_id"
   )
   SELECT c."customer_name", a.total_sales 
   FROM "Customers" c 
   INNER JOIN AggregatedSales a ON c."id" = a."customer_id";

5. **Aggregation & Filtering Rules:**
   - Always include GROUP BY when using aggregate functions.
   - For filtering aggregates, use HAVING clause AFTER GROUP BY.

6. **Null Handling:**
   - Use NULLS LAST ONLY inside ORDER BY clauses (e.g., ORDER BY amount DESC NULLS LAST). 
   - NULLS LAST is INVALID after GROUP BY.

7. **Error Fallback:**
   - If the question asks for columns/data not present in the schema, or requires a JOIN path that does not exist in the relationships context, do NOT guess.
   - Return EXACTLY this query: SELECT 'Error: Cannot answer this question with available data.' AS error;

8. **Output Constraint (STRICT):**
   - Return ONLY the raw PostgreSQL query.
   - Start immediately with 'SELECT' or 'WITH'.
   - Do NOT wrap the output in markdown code blocks (```sql).
   - Do NOT output any reasoning, preamble, or postscript text.

9. **Single Query Constraint (CRITICAL):**
   -You MUST return exactly ONE single, unified SQL statement. 
   -NEVER return multiple separate queries separated by semicolons.
   -If the user asks for multiple different metrics (e.g., "highest AND lowest"), you must combine the results into a single query using UNION ALL, subqueries, or conditional aggregation.
   -The entire response must end with exactly one semicolon.

10. **Type Casting for Math & Rounding:**
    -In PostgreSQL, the ROUND(value, decimal_places) function strictly requires a NUMERIC type. If you are calculating percentages or dividing numbers, you MUST explicitly cast the mathematical result to numeric BEFORE rounding.
    -❌ Incorrect: ROUND((a / b) * 100, 2)
    -✅ Correct: ROUND(((a / b) * 100)::numeric, 2)

12. **Revenue, Currency Handling:**
      - If the question involves revenue or currency, ensure that you are using ₹ for currency symbols in your output.

### USER QUESTION:
{question}

### POSTGRESQL QUERY:
"""

MULTI_TABLE_SQL_PROMPT = ChatPromptTemplate.from_template(MULTI_TABLE_SQL_PROMPT_TEMPLATE)


def format_relationships_context(relationships: List[Dict]) -> str:
    """Format relationships into readable context for LLM."""
    if not relationships:
        return "No relationships detected. Tables are independent."
    
    context = "APPROVED JOIN CONDITIONS:\n"
    for i, rel in enumerate(relationships, 1):
        context += f"{i}. {rel['from_sheet']}.{rel['from_column']} = {rel['to_sheet']}.{rel['to_column']}\n"
    
    return context
