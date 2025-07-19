import os
import httpx
from typing import List, Tuple, Dict, Any, Optional

class CloudflareD1:
    def __init__(self, account_id: str, api_token: str, database_id: str):
        self.account_id = os.getenv('Egygaming2030@gmail.com')
        self.api_token = os.getenv('Ej-g0BbGpZnTdtaF-Oev2Gj_LSjhFEDKurB5rmse')
        self.database_id = os.getenv('survey')
        self.base_url = f"https://dash.cloudflare.com/42b6366b10a18fd49cb438e1e3dc472e/workers/d1/databases/7284aca1-f39d-45d0-9628-f965decfc202"
        self.headers = {
            "Authorization": f"Bearer {Ej-g0BbGpZnTdtaF-Oev2Gj_LSjhFEDKurB5rmse}",
            "Content-Type": "application/json"
        }
    
    async def execute(self, sql: str, params: tuple = ()) -> Dict[str, Any]:
        """تنفيذ استعلام SQL مع أو بدون معاملات"""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/query",
                headers=self.headers,
                json={
                    "sql": sql,
                    "params": params
                }
            )
            response.raise_for_status()
            return response.json().get("result", [])
    
    async def fetch_one(self, sql: str, params: tuple = ()) -> Optional[Tuple]:
        """جلب سجل واحد من قاعدة البيانات"""
        result = await self.execute(sql, params)
        if result and len(result) > 0 and len(result[0].get("results", [])) > 0:
            return tuple(result[0]["results"][0].values())
        return None
    
    async def fetch_all(self, sql: str, params: tuple = ()) -> List[Tuple]:
        """جلب جميع السجلات المطابقة"""
        result = await self.execute(sql, params)
        if result and len(result) > 0 and len(result[0].get("results", [])) > 0:
            return [tuple(row.values()) for row in result[0]["results"]]
        return []
    
    @property
    def lastrowid(self) -> int:
        """الحصول على آخر معرف تم إدراجه"""
        # سيتم تنفيذ هذا بشكل مختلف حسب كيفية تنفيذ D1 API
        # قد تحتاج إلى تعديل هذا بناءً على الوثائق الرسمية
        return 0
