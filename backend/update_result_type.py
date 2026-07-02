import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pymysql
from quant.services.performance_analysis import DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME

print('Updating result_type based on score...')
try:
    conn = pymysql.connect(host=DB_HOST, port=DB_PORT, user=DB_USER, password=DB_PASSWORD, database=DB_NAME)
    cursor = conn.cursor()
    
    sql = """
        UPDATE stock_deep_analysis
        SET result_type = CASE
            WHEN score >= 100 THEN 'SS级'
            WHEN score >= 90 AND score <= 99 THEN 'S级'
            WHEN score >= 80 AND score <= 89 THEN 'A级'
            WHEN score >= 65 AND score <= 79 THEN 'B级'
            WHEN score >= 50 AND score <= 64 THEN 'C级'
            WHEN score > 0 AND score < 50 THEN 'D级'
            ELSE result_type
        END
        WHERE score > 0;
    """
    
    cursor.execute(sql)
    affected_rows = cursor.rowcount
    conn.commit()
    conn.close()
    
    print(f'Update finished successfully. Affected rows: {affected_rows}')
except Exception as e:
    print(f'Update error: {e}')
