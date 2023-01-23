const st = {};

st.flap = document.querySelector('#flap');
st.toggle = document.querySelector('.toggle');

st.choice2 = document.querySelector('#multi');
st.choice1 = document.querySelector('#recurring');

if (typeof st.flap !== 'undefined' &&  st.flap !== null){
    st.flap.addEventListener('transitionend', () => {
        if (st.choice1.checked) {
            st.toggle.style.transform = 'rotateY(-15deg)';
            setTimeout(() => st.toggle.style.transform = '', 400);
        } else {
            st.toggle.style.transform = 'rotateY(15deg)';
            setTimeout(() => st.toggle.style.transform = '', 400);
        }

    })

    st.clickHandler = (e) => {

        if (e.target.tagName === 'LABEL') {
            setTimeout(() => {

                st.flap.children[0].textContent = e.target.textContent;
            }, 250);
        }
    }


    if (document.readyState !== "loading") {
        st.flap.children[0].textContent = st.choice2.nextElementSibling.textContent;
        document.addEventListener('click', (e) => st.clickHandler(e));
    //    output.innerHTML = slider.value; // Display the default slider value
    } else {
        document.addEventListener('DOMContentLoaded', () => {
            st.flap.children[0].textContent = st.choice2.nextElementSibling.textContent;
            document.addEventListener('click', (e) => st.clickHandler(e));
        //    output.innerHTML = slider.value; // Display the default slider value
        });
    }
}









