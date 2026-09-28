// 既存の相性コードと色を維持。入力画面には表がないので、その場合は何もしない。
function hantei() {
  const table1 = document.getElementById("kanteitable");
  if (!table1) return;
  for (const row of table1.rows) {
    for (const cell of row.cells) {
      if (cell.id === "chk") {
        if (cell.innerText === "1") cell.style.backgroundColor = "#FF0000";
        else if (cell.innerText === "2") cell.style.backgroundColor = "#FF7F00";
        else if (cell.innerText === "3") cell.style.backgroundColor = "#ffffff";
      }
    }
  }
}
