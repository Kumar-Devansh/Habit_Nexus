// function toggleMode() {

//     document.body.classList.toggle("light-mode");

//     if (
//         document.body.classList.contains(
//             "light-mode"
//         )
//     ) {
//         localStorage.setItem(
//             "theme",
//             "light"
//         );
//     } else {
//         localStorage.setItem(
//             "theme",
//             "dark"
//         );
//     }
// }

// document.addEventListener(
//     "DOMContentLoaded",
//     function () {

//         const theme =
//             localStorage.getItem(
//                 "theme"
//             );

//         if (theme === "light") {
//             document.body.classList.add(
//                 "light-mode"
//             );
//         }
//     }
// );
function toggleMode(){

    document.body.classList.toggle(
        "light-mode"
    );

    localStorage.setItem(
        "theme",
        document.body.classList.contains(
            "light-mode"
        )
        ? "light"
        : "dark"
    );
}

document.addEventListener(
    "DOMContentLoaded",
    () => {

        if(
            localStorage.getItem(
                "theme"
            ) === "light"
        ){

            document.body.classList.add(
                "light-mode"
            );
        }
    }
);